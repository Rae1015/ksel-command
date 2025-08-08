from fastapi import FastAPI, Request
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    model_name = data.get("text", "").strip()

    if not model_name:
        return {"text": "모델명을 입력해주세요. 예: /ksel KTC-K501"}

    search_url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"

    payload = {
        "searchKey": "03",           # 모델명 조건검색
        "searchKeyword": model_name,
        "currentPage": "1"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(search_url, data=payload)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            return {"text": f"🔍 [{model_name}] 검색 결과가 없습니다."}

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

        final_message = "\n\n".join(results)
        return {"text": final_message}
