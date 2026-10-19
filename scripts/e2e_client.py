"""MCP stdio 클라이언트로 서버의 도구를 실제 호출해 보는 테스트 스크립트.
1) 정보가 부족한 상태에서는 install_footer_popup이 설치를 거부하는지 확인
2) 교사 답변(예시 정보)을 넣어 [확인 필요]를 모두 채운 뒤 팝업이 설치되는지 확인"""
import asyncio, json, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

APP = sys.argv[1] if len(sys.argv) > 1 else "./sample-app"
BASIC = {"operator_name": "홍길동", "school": "○○초등학교", "contact_phone": "02-000-0000", "purpose": "초등학생 글쓰기 수업용"}
FULL = dict(BASIC, **{
    "app_name": "쑥쑥 글쓰기 친구",
    "contact_email": "teacher@example.sen.go.kr",
    "delete_method": "브라우저 설정의 '사이트 데이터 삭제'로 즉시 지울 수 있으며, 담당 교사에게 요청하면 함께 삭제를 도와드립니다.",
    "effective_date": "2026년 11월 1일",
    "retention": "해당 학년도 종료 시까지(이용자가 기록을 지우면 즉시 삭제)",
    "features": "학생 이름 입력, 글쓰기, 외부 AI를 이용한 글쓰기 피드백, 활동 기록을 이용자 기기에 저장",
    "consent_method": "학년 초 가정통신문(개인정보 수집·이용 및 국외 이전 동의서)으로 보호자 동의를 받음",
    "ai_sends_name": False,
    "ai_retention": "API 요청 데이터는 제공자 정책에 따라 최대 30일 보관 후 삭제되며 모델 학습에 사용되지 않음",
    "ai_transfer_type": "처리위탁",
    "api_key_in_server": True,
    "access_url": "https://example.vercel.app",
    "grade_fit": "초등 3~6학년 국어 글쓰기 단원 활동",
    "content_safety": "AI 응답은 참고용임을 이용약관에 안내하고, 교사가 수업 중 응답을 함께 확인",
    "device_env": "설치 없이 크롬·웨일 브라우저에서 사용, PC·태블릿 반응형 화면",
    "support_material": "학생용 사용 안내 1쪽(수업 중 배부)",
})


async def call(s, name, args):
    res = await s.call_tool(name, args)
    txt = res.content[0].text
    print(f"\n=== {name} (error={getattr(res, 'is_error', getattr(res, 'isError', None))}) ===\n{txt[:1500]}")
    return json.loads(txt)


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "edu_legal_mcp.server"], cwd=str(Path(__file__).resolve().parents[1]))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            await call(s, "analyze_app", {"project_path": APP})
            # 1) 정보 부족 → 설치 거부
            d = await call(s, "write_legal_docs", {"project_path": APP, "info": BASIC})
            assert d["unresolved_count"] > 0
            p = await call(s, "install_footer_popup", {"project_path": APP, "include_checklist": True})
            assert p["installed"] is False, "확인 필요가 남았는데 설치됨"
            # 2) 교사 답변 반영 → 설치
            d = await call(s, "write_legal_docs", {"project_path": APP, "info": FULL})
            assert d["unresolved_count"] == 0, d["questions"]
            c = await call(s, "generate_checklists", {"project_path": APP, "info": FULL})
            p = await call(s, "install_footer_popup", {"project_path": APP, "include_checklist": True})
            assert p["installed"] is True and not p["skipped"], p
            print("\nE2E OK")

asyncio.run(main())
