"""MCP stdio 클라이언트로 서버의 도구를 실제 호출해 보는 테스트 스크립트."""
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

APP = sys.argv[1] if len(sys.argv) > 1 else "./sample-app"
INFO = {"operator_name": "홍길동", "school": "○○초등학교", "contact_phone": "02-000-0000", "purpose": "초등학생 글쓰기 수업용"}

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "edu_legal_mcp.server"], cwd=str(__import__('pathlib').Path(__file__).resolve().parents[1]))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            for name, args in [("analyze_app", {"project_path": APP}),
                               ("draft_legal_docs", {"project_path": APP, "info": INFO}),
                               ("generate_checklists", {"project_path": APP, "info": INFO}),
                               ("install_footer_popup", {"project_path": APP, "include_checklist": True})]:
                res = await s.call_tool(name, args)
                txt = res.content[0].text
                print(f"\n=== {name} (error={getattr(res, "is_error", getattr(res, "isError", None))}) ===\n{txt[:1800]}")

asyncio.run(main())
