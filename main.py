import os
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import httpx
from bs4 import BeautifulSoup
import uvicorn

# --------------------------------
# FastAPI 앱 + 로거 설정
# --------------------------------
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# 전역 httpx AsyncClient
client = httpx.AsyncClient(
    timeout=5.0,
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
        keepalive_expiry=30.0
    )
)

SEARCH_URL = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"


# --------------------------------
# 헬스체크 (/)
# --------------------------------
@app.api_route("/", methods=["GET", "HEAD"])
async def health_check(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200)
    return JSONResponse({"status": "✅ KSEL bot is running"})


# --------------------------------
# 모델 정보 조회
# --------------------------------
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


# --------------------------------
# Dooray 슬래시커맨드 엔드포인트
# --------------------------------
@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    logging.info(f"📥 Request Payload: {data}")  # payload 확인

    model_name = data.get("text", "").strip()
    response_url = data.get("response_url")  # Dooray에서 내려주는 키
    logging.info(f"📌 response_url = {response_url}")

    if not model_name:
        return {
            "deleteOriginal": True,
            "text": "모델명을 입력해주세요. 예: /ksel ktc-k501"
        }

    # 1) 먼저 "검색중입니다" 메시지 반환 (Dooray에 즉시 응답)
    asyncio.create_task(handle_search(model_name, response_url))
    return {
        "responseType": "inChannel",
        "text": f"⏳ [{model_name}] 검색중입니다..."
    }


# --------------------------------
# 검색 처리 후 response_url에 최종 결과 전송
# --------------------------------
async def handle_search(model_name: str, response_url: str):
    try:
        result = await asyncio.wait_for(fetch_model_info(model_name), timeout=5.0)
    except asyncio.TimeoutError:
        result = f"⚠️ [{model_name}] 조회 중 응답이 지연되었습니다. 잠시 후 다시 시도해주세요."

    if response_url:
        try:
            await client.post(
                response_url,
                json={
                    "replaceOriginal": True,   # 기존 메시지 교체
                    "responseType": "inChannel",
                    "text": result
                }
            )
            logging.info(f"✅ 결과 전송 완료 → {response_url}")
        except Exception as e:
            logging.error(f"❌ response_url 전송 실패: {e}")


# --------------------------------
# 서버 실행
# --------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
