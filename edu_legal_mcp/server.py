"""edu-legal-mcp: 교사 개발자 웹앱용 이용약관·개인정보처리방침·필수기준 체크리스트 MCP 서버 (stdio)."""
from __future__ import annotations
import json
from typing import Any
try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
from . import analyzer, legal, popup, checklists

mcp = _Server("edu-legal-mcp", instructions=(
    "교사가 만든 웹앱을 분석해 ① 이용약관·개인정보처리방침 초안 ② 하단 링크+팝업 ③ 에듀집/학교용 필수기준 체크리스트(HWPX)를 만듭니다. "
    "순서: analyze_app → draft_legal_docs → (교사 확인) → install_footer_popup → generate_checklists. "
    "[확인 필요] 항목은 반드시 교사에게 질문하고, 절대 배포·게시·제출하지 마세요."))

INFO_DOC = ("info(선택): app_name, operator_name(개발 교사 성명), school, contact_phone(교무실 등 공용 번호), contact_email, "
            "effective_date(시행일), purpose(학생 수업용/행정업무용), retention(보유 기간), access_url, summary")


def _j(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, indent=2)


@mcp.tool()
def analyze_app(project_path: str) -> str:
    """웹앱 프로젝트 폴더(로컬 경로)를 분석합니다. 입력 항목(이름 등), 브라우저 저장소, 외부 AI API, Firebase/Supabase, 로그인,
    외부 전송 주소, 프레임워크와 화면 스타일(글꼴·색·모서리)을 근거(파일:줄)와 함께 돌려줍니다. 결과는 legal-docs/analysis.json에도 저장됩니다."""
    a = analyzer.analyze(project_path)
    (legal.out_dir(project_path) / "analysis.json").write_text(_j(a), "utf-8")
    return _j(a)


@mcp.tool()
def draft_legal_docs(project_path: str, info: dict | None = None) -> str:
    """분석 결과를 바탕으로 이용약관·개인정보처리방침 초안을 legal-docs/에 마크다운과 HWPX(한글)로 만듭니다.
    예시 문서의 구조만 따르며 기능·연락처·보관기간은 실제 앱/교사 정보로만 채우고, 모르는 내용은 [확인 필요]와 질문 목록으로 남깁니다.
    게시·배포하지 않습니다.
    info(선택): app_name, operator_name(개발 교사 성명), school, contact_phone(교무실 등 공용 번호), contact_email, effective_date(시행일), purpose(학생 수업용/행정업무용), retention(보유 기간), access_url, summary"""
    a = analyzer.analyze(project_path)
    r = legal.write(project_path, a, info)
    r["next"] = "질문에 답을 받아 info로 다시 실행한 뒤, install_footer_popup으로 하단에 연결하세요."
    return _j(r)


@mcp.tool()
def install_footer_popup(project_path: str, include_checklist: bool = True, html_file: str | None = None) -> str:
    """확인한 이용약관·개인정보처리방침을 웹앱 하단 링크로 연결하고, 누르면 앱의 글꼴·색·모서리에 맞춘 팝업으로 엽니다
    (끝까지 스크롤하면 '확인했어요' 활성화, ×/Esc로 닫기, 휴대전화에서는 아래에서 올라오는 시트). include_checklist=true면
    체크리스트(검토용) 팝업 링크도 추가합니다. 배포하지 않습니다."""
    a = analyzer.analyze(project_path)
    return _j(popup.install(project_path, a, include_checklist, html_file))


@mcp.tool()
def generate_checklists(project_path: str, info: dict | None = None) -> str:
    """에듀집 필수기준 체크리스트(개인정보 있는/없는 웹앱 양식 자동 선택)와 학교용 필수기준 체크리스트를 원본 표 형식 그대로
    HWPX로 만듭니다. 각 답변에 근거(처리방침 조문·파일:줄)를 적고, 확인 못한 항목은 [확인 필요], 기능이 없을 때만 [해당 없음].
    학교용은 '검토 초안'으로 표시하며 선택기준은 학교 판단 영역으로 비워 둡니다. 제출하지 않습니다.
    info(선택): draft_legal_docs와 같음(생략 시 마지막 draft 정보 사용)."""
    a = analyzer.analyze(project_path)
    if info is None:
        p = legal.out_dir(project_path) / "draft_meta.json"
        info = json.loads(p.read_text("utf-8")).get("info") if p.exists() else {}
    return _j(checklists.generate(project_path, a, info))


@mcp.tool()
def run_all(project_path: str, info: dict | None = None, include_checklist_link: bool = True) -> str:
    """analyze_app → draft_legal_docs → generate_checklists → install_footer_popup을 한 번에 실행합니다(검토용 초안)."""
    a = analyzer.analyze(project_path)
    (legal.out_dir(project_path) / "analysis.json").write_text(_j(a), "utf-8")
    d = legal.write(project_path, a, info)
    c = checklists.generate(project_path, a, info)
    p = popup.install(project_path, a, include_checklist_link)
    return _j({"variant": a["checklist_variant"], "docs": d["files"], "checklists": c["files"], "popup": p,
               "questions": d["questions"] + c["questions"]})


def main():
    mcp.run()


if __name__ == "__main__":
    main()
