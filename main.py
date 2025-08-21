import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import httpx
from bs4 import BeautifulSoup
import uvicorn

app = FastAPI()

client = httpx.AsyncClient(timeout=5.0)

SEARCH_URL = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"


@app.api_route("/", methods=["GET", "HEAD"])
async def health_check(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200)
    return JSONResponse({"status": "✅ KSEL bot is running"})


async def fetch_model_info(model_name: str) -> str:
    payload = {"searchKey": "03", "searchValue": model_name, "currentPage": "1"}
    response = await client.post(SEARCH_URL, data=payload)
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    if "검색된 건이 없습니다." in soup.get_text(strip=True) or not rows:
        return f"🔍 [{model_name}] 검색 결과가 없습니다."

    results = []
    for row in rows[:10]:
        cols = row.find_all("td")
        if len(cols) >= 8:
            cert_no = cols[2].text.strip()
            identifier = cols[3].text.strip().split()[0]
            model = cols[5].text.strip().split()[0]
            date_parts = cols[6].text.strip().split()
            cert_date = date_parts[0]
            exp_date = date_parts[1] if len(date_parts) > 1 else ""
            results.append(
                f"[{cert_no}] {model}\n"
                f" - 식별번호 : {identifier}\n"
                f" - 인증일자 : {cert_date}\n"
                f" - 만료일자 : {exp_date}"
            )
    return "\n\n".join(results)


@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    model_name = data.get("text", "").strip()
    response_url = data.get("response_url")  # ✅ Dooray가 보내줌

    if not model_name:
        return {"text": "모델명을 입력해주세요. 예: /ksel ktc-k501"}

    # 1️⃣ 먼저 "검색중입니다..." 메시지 즉시 반환
    asyncio.create_task(background_search(model_name, response_url))
    return {"text": f"🔍 [{model_name}] 검색중입니다..."}


async def background_search(model_name: str, response_url: str):
    try:
        result = await asyncio.wait_for(fetch_model_info(model_name), timeout=5.0)
    except asyncio.TimeoutError:
        result = f"⚠️ [{model_name}] 조회 중 응답이 지연되었습니다."

    # 2️⃣ 검색 결과를 response_url로 POST (Dooray에 새 메시지 전송)
    if response_url:
        async with httpx.AsyncClient() as c:
            await c.post(response_url, json={"text": result})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
