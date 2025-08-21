import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import httpx
from bs4 import BeautifulSoup
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ------------------------------
# 전역 AsyncClient (비동기 연결 풀)
# ------------------------------
client = httpx.AsyncClient(
    timeout=5.0,
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30.0)
)

SEARCH_URL = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"

# ------------------------------
# 헬스체크 루트 (/)
# ------------------------------
@app.api_route("/", methods=["GET", "HEAD"])
async def health_check(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200)
    return JSONResponse({"status": "✅ KSEL bot is running"})


# ------------------------------
# 크레피아 모델 정보 조회
# ------------------------------
async def fetch_model_info(model_name: str) -> str:
    payload = {"searchKey": "03", "searchValue": model_name, "currentPage": "1"}
    response = await client.post(SEARCH_URL, data=payload)
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    no_result_text = soup.get_text(strip=True)
    if "검색된 건이 없습니다." in no_result_text or not rows:
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


# ------------------------------
# 슬래시 커맨드 엔드포인트
# ------------------------------
@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    logger.info(f"📥 Request Payload: {data}")

    model_name = data.get("text", "").strip()
    response_url = data.get("responseUrl")
    channel_id = data.get("channelId")

    if not model_name:
        return {"deleteOriginal": True, "text": "모델명을 입력해주세요. 예: /ksel ktc-k501"}

    # 1️⃣ 검색중 메시지 송신
    try:
        if response_url and channel_id:
            await client.post(response_url, json={
                "channelId": channel_id,
                "text": f"🔍 [{model_name}] 검색중입니다...",
                "replaceOriginal": False
            })
    except Exception as e:
        logger.error(f"검색중 메시지 전송 실패: {e}")

    # 2️⃣ 검색 실행
    try:
        result = await asyncio.wait_for(fetch_model_info(model_name), timeout=3.0)
    except asyncio.TimeoutError:
        result = f"⚠️ [{model_name}] 조회 중 응답이 지연되었습니다. 잠시 후 다시 시도해주세요."

    # 3️⃣ 이전 메시지 교체
    try:
        if response_url and channel_id:
            await client.post(response_url, json={
                "channelId": channel_id,
                "text": result,
                "replaceOriginal": True
            })
    except Exception as e:
        logger.error(f"검색 결과 메시지 전송 실패: {e}")

    # 슬래시 커맨드에 바로 응답
    return JSONResponse({"deleteOriginal": True})


# ------------------------------
# 서버 실행
# ------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
