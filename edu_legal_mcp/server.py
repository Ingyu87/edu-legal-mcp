"""edu-legal-mcp: 교사 개발자 웹앱용 이용약관·개인정보처리방침·필수기준 체크리스트 MCP 서버 (stdio)."""
from __future__ import annotations
import json
from typing import Any
try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
from . import analyzer, legal, popup, checklists


def _save_analysis(project_path: str, a: dict) -> None:
    # 배포 폴더에 같이 올라가도 PC 사용자 이름·절대 경로가 드러나지 않도록 project_path는 빼고 저장
    (legal.out_dir(project_path) / "analysis.json").write_text(_j({k: v for k, v in a.items() if k != "project_path"}), "utf-8")

mcp = _Server("edu-legal-mcp", instructions=(
    "교사가 만든 웹앱을 분석해 ① 이용약관·개인정보처리방침 ② 하단 링크+팝업 ③ 에듀집/학교용 필수기준 체크리스트(HWPX)를 만듭니다. "
    "순서: analyze_app → write_legal_docs → (questions를 교사에게 질문하고 답을 info로 넣어 다시 실행) → install_footer_popup → generate_checklists. "
    "만든 문서는 실제 앱에 그대로 붙는 최종본입니다. " + legal.AI_RULE + " 배포·게시·제출은 교사가 직접 합니다."))

INFO_DOC = ("info(선택): app_name, operator_name(개발 교사 성명), school, contact_phone(교무실 등 공용 번호), contact_email, "
            "effective_date(시행일), purpose(학생 수업용/행정업무용), retention(보유 기간), features(주요 기능 확정 문구), "
            "consent_method(만 14세 미만 보호자 동의 방식), ai_sends_name(true/false), ai_retention(외부 AI 데이터 보관 정책), "
            "ai_transfer_type('처리위탁' 또는 '제3자 제공'), api_key_in_server(true/false), server_location, withdrawal_method, delete_method(기록 삭제 방법 안내 문장), "
            "access_url, summary, 학교용 체크리스트 교사 답변: grade_fit, content_safety, device_env, support_material")


def _j(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, indent=2)


def _doc(extra: str):
    def deco(f):
        f.__doc__ = (f.__doc__ or "") + "\n" + extra
        return f
    return deco


@mcp.tool()
def analyze_app(project_path: str) -> str:
    """웹앱 프로젝트 폴더(로컬 경로)를 분석합니다. 입력 항목(이름 등), 브라우저 저장소, 외부 AI API, Firebase/Supabase, 로그인,
    외부 전송 주소, 프레임워크와 화면 스타일(글꼴·색·모서리)을 근거(파일:줄)와 함께 돌려줍니다. 결과는 legal-docs/analysis.json에도 저장됩니다."""
    a = analyzer.analyze(project_path)
    _save_analysis(project_path, a)
    return _j(a)


@mcp.tool()
@_doc(INFO_DOC + "\n" + legal.AI_RULE)
def write_legal_docs(project_path: str, info: dict | None = None) -> str:
    """분석 결과를 바탕으로 이용약관·개인정보처리방침을 legal-docs/에 마크다운과 HWPX(이용약관.hwpx, 개인정보처리방침.hwpx)로 만듭니다.
    시행일이 들어간 최종본 형식이며, 예시 문서의 구조만 따르고 기능·연락처·보관기간은 실제 앱/교사 정보로만 채웁니다.
    모르는 내용은 [확인 필요]와 questions(교사에게 할 질문)로 남깁니다. 게시·배포하지 않습니다."""
    a = analyzer.analyze(project_path)
    r = legal.write(project_path, a, info)
    r["next"] = ("questions를 교사에게 하나씩 묻고 답을 info에 넣어 다시 실행하세요. unresolved_count가 0이 되면 install_footer_popup으로 하단에 연결하세요."
                 if r["unresolved_count"] else "모든 항목이 채워졌습니다. install_footer_popup으로 하단에 연결하세요.")
    return _j(r)


@mcp.tool()
@_doc(legal.AI_RULE)
def install_footer_popup(project_path: str, include_checklist: bool = False, html_file: str | None = None) -> str:
    """이용약관·개인정보처리방침을 웹앱 하단 링크로 연결하고, 누르면 앱의 글꼴·색·모서리에 맞춘 팝업으로 엽니다
    (끝까지 스크롤하면 '확인했어요' 활성화, ×/Esc로 닫기, 휴대전화에서는 아래에서 올라오는 시트).
    문서에 [확인 필요]나 '초안' 같은 표현이 남아 있으면 설치하지 않고, 교사에게 물어볼 질문을 돌려줍니다.
    include_checklist=true면 에듀집 체크리스트 팝업 링크도 추가합니다(체크리스트에 [확인 필요]가 남으면 그 링크만 빼고 설치). 배포하지 않습니다."""
    a = analyzer.analyze(project_path)
    return _j(popup.install(project_path, a, include_checklist, html_file))


@mcp.tool()
@_doc(legal.AI_RULE)
def generate_checklists(project_path: str, info: dict | None = None) -> str:
    """에듀집 필수기준 체크리스트(개인정보 있는/없는 웹앱 양식 자동 선택)와 학교용 필수기준 체크리스트를 원본 표 형식 그대로
    HWPX로 만듭니다. 각 답변에 근거(처리방침 조문·파일:줄)를 적고, 확인 못한 항목은 [확인 필요], 기능이 없을 때만 [해당 없음].
    학교용 선택기준의 확인란과 '학교 확인(학교 작성)' 칸은 학교가 심의하며 채우도록 비워 둡니다. 제출하지 않습니다.
    info(선택): write_legal_docs와 같음(생략 시 마지막으로 쓴 정보 사용)."""
    a = analyzer.analyze(project_path)
    if info is None:
        info = legal.read_meta(project_path)
    return _j(checklists.generate(project_path, a, info))


@mcp.tool()
@_doc(legal.AI_RULE)
def run_all(project_path: str, info: dict | None = None, include_checklist_link: bool = False) -> str:
    """analyze_app → write_legal_docs → generate_checklists → install_footer_popup을 한 번에 실행합니다.
    [확인 필요]가 남아 있으면 팝업 설치는 거부되고 교사에게 할 질문이 돌아옵니다."""
    a = analyzer.analyze(project_path)
    _save_analysis(project_path, a)
    d = legal.write(project_path, a, info)
    c = checklists.generate(project_path, a, info)
    p = popup.install(project_path, a, include_checklist_link)
    return _j({"variant": a["checklist_variant"], "docs": d["files"], "checklists": c["files"], "popup": p,
               "questions": d["questions"] + c["questions"], "rule": legal.AI_RULE})


def main():
    mcp.run()


if __name__ == "__main__":
    main()
