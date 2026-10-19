"""샘플 앱에서 팝업 3종을 열고 캡처합니다."""
import asyncio, sys
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/workspace/shots"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=1)
        await pg.goto(URL); await pg.wait_for_load_state("networkidle")
        for i, (key, fn, scroll) in enumerate([("terms", "1_terms.png", 0), ("privacy", "2_privacy.png", 0), ("checklist", "3_checklist.png", 260)]):
            await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await pg.click(f'[data-el="{key}"]')
            await pg.wait_for_selector(".el-m")
            await pg.evaluate(f"document.querySelector('.el-b').scrollTop={scroll}")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"{OUT}/{fn}")
            await pg.keyboard.press("Escape")
            assert await pg.query_selector(".el-m") is None
        # 모바일: 열고 끝까지 스크롤 → 확인 버튼 활성화 → 닫기
        m = await b.new_page(viewport={"width": 390, "height": 760}, is_mobile=True, has_touch=True)
        await m.goto(URL); await m.wait_for_load_state("networkidle")
        await m.click('[data-el="privacy"]')
        assert await m.is_disabled(".el-ok")
        await m.evaluate("const b=document.querySelector('.el-b'); b.scrollTop=b.scrollHeight")
        await m.wait_for_timeout(200)
        assert not await m.is_disabled(".el-ok")
        await m.screenshot(path=f"{OUT}/4_mobile_privacy_end.png")
        await m.click(".el-ok")
        assert await m.query_selector(".el-m") is None
        print("mobile ok")
        await b.close()
asyncio.run(main())
