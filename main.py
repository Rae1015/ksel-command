import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def search_crefia_model(model_name):
    url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # headless=False로 하면 브라우저 창 열림
        page = await browser.new_page()

        await page.goto(url)

        # 조건검색 select 박스에서 '모델명' 선택 (value=03)
        await page.select_option("#FindSlct", "03")

        # 검색어 입력란에 모델명 입력
        await page.fill("input[name=searchKeyword]", model_name)

        # 검색 버튼 클릭
        await page.click("button[type=submit]")

        # 검색 결과 로딩 대기 (적절한 셀렉터로 변경 가능)
        await page.wait_for_selector("table tbody tr")

        # 결과 페이지 HTML 가져오기
        content = await page.content()

        await browser.close()

        # BeautifulSoup 으로 테이블 파싱
        soup = BeautifulSoup(content, "html.parser")
        rows = soup.select("table tbody tr")

        results = []
        for row in rows[:10]:
            cols = row.find_all("td")
            if len(cols) >= 8:
                cert_no = cols[1].text.strip()
                model = cols[3].text.strip()
                version = cols[4].text.strip()
                identifier = cols[2].text.strip()
                cert_date = cols[5].text.strip()
                exp_date = cols[6].text.strip()

                result_text = (
                    f"[{cert_no}]\n"
                    f"{model} ({version})\n"
                    f"{identifier}\n"
                    f"인증일자 : {cert_date}\n"
                    f"만료일자 : {exp_date}"
                )
                results.append(result_text)

        return "\n\n".join(results)

# 테스트 실행
if __name__ == "__main__":
    model = "KTC-K501"
    result = asyncio.run(search_crefia_model(model))
    print(result)
