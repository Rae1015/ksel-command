from fastapi import FastAPI, Request
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    text = data.get("text")
    if not text:
        return {"text": "❗ 모델명을 입력해주세요. 예: /ksel SZZZZ123"}

    model_name = text.strip()
    search_url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"

    async with httpx.AsyncClient() as client:
        response = await client.post(search_url, data={"searchKeyword": model_name})
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            return {"text": f"🔍 [{model_name}] 검색 결과가 없습니다."}

        # 모든 검색 결과를 문자열로 합치기
        results = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 4:
                result_text = (
                    f"📌 모델명: {cols[0].text.strip()}\n"
                    f"🏢 제조사: {cols[1].text.strip()}\n"
                    f"📅 등록일: {cols[2].text.strip()}\n"
                    f"⏳ 만료일: {cols[3].text.strip()}"
                )
                results.append(result_text)

        # Dooray 메시지는 하나의 문자열로 반환해야 하므로 join
        final_message = "\n\n".join(results)

        return {"text": final_message}
