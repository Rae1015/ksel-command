from fastapi import FastAPI, Request
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    text = data.get("text")
    if not text:
        return {"text": "❗ 모델명을 입력해주세요. 예: /ksel KTC-K501"}

    model_name = text.strip()
    search_url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"

    async with httpx.AsyncClient() as client:
        response = await client.post(search_url, data={"searchKeyword": model_name})
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            return {"text": f"🔍 [{model_name}] 검색 결과가 없습니다."}

        results = []
        # 최대 10개의 결과만 처리
        for row in rows[:10]:
            cols = row.find_all("td")
            if len(cols) >= 8:
                cert_no = cols[1].text.strip()          # 인증번호
                model = cols[3].text.strip()           # 모델명
                version = cols[4].text.strip()         # 버전
                identifier = cols[2].text.strip()     # 단말기식별번호
                cert_date = cols[5].text.strip()       # 인증일자
                exp_date = cols[6].text.strip()        # 만료일자

                results.append((
                    f"[{cert_no}]\n"
                    f"{model} ({version})\n"
                    f"{identifier}\n"
                    f"인증일자 : {cert_date}\n"
                    f"만료일자 : {exp_date}"
                ))

        final_message = "\n\n".join(results)
        return {"text": final_message}