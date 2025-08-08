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
        #"searchKeyword": model_name,
        "searchValue": model_name,
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
                #cert_type = cols[1].text.strip()
                cert_no = cols[2].text.strip()
                identifier = cols[3].text.strip()
                model_raw = cols[5].text.strip()
                model = model_raw.split()[0]
                date_raw = cols[6].text.strip()   # "2025.06.22\n\n2027.06.22"
                cert_date = date_raw.split()[0]  # 공백(엔터, 스페이스) 기준으로 분리 후 첫 항목
                exp_date = date_raw.split()[3] 

                result_text = (
                    f"[{cert_no}] {model}"
                    f"식별번호 : {identifier}\n"
                    f"인증일자 : {cert_date}\n"
                    f"만료일자 : {exp_date}"
                )
                results.append(result_text)

        final_message = "\n\n".join(results)
        return {"text": final_message}
