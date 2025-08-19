import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
import httpx
from bs4 import BeautifulSoup
import uvicorn
from collections import OrderedDict

app = FastAPI()

# 전역 AsyncClient (비동기 연결 풀)
client = httpx.AsyncClient(
    timeout=5.0,
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
        keepalive_expiry=30.0
    )
)

# 최근 검색 캐시 (최대 20개 저장)
cache = OrderedDict()
CACHE_LIMIT = 20

SEARCH_URL = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"


async def do_warmup():
    """
    크레피아 사이트 호출해서 연결 풀 유지
    """
    try:
        payload = {"searchKey": "03", "searchValue": "test", "currentPage": "1"}
        resp = await client.post(SEARCH_URL, data=payload)
        if resp.status_code == 200:
            print(f"✅ 예열 성공 ({datetime.now().strftime('%H:%M:%S')})")
        else:
            print(f"⚠️ 예열 실패 (status: {resp.status_code})")
    except Exception as e:
        print(f"❌ 예열 오류: {e}")


@app.on_event("startup")
async def startup_event():
    """
    서버 시작 시 1회 예열 + 스케줄러 시작
    """
    await do_warmup()
    asyncio.create_task(warmup_scheduler())


async def warmup_scheduler():
    """
    8시~20시 사이 1시간마다 예열 실행
    """
    while True:
        now = datetime.now()
        if 8 <= now.hour <= 20:
            await do_warmup()
        await asyncio.sleep(3600)  # 1시간 대기


async def fetch_model_info(model_name: str) -> str:
    """
    크레피아 사이트에서 모델 정보 조회
    """
    payload = {"searchKey": "03", "searchValue": model_name, "currentPage": "1"}

    response = await client.post(SEARCH_URL, data=payload)
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    # "검색된 건이 없습니다." 문구 확인
    no_result_text = soup.get_text(strip=True)
    if "검색된 건이 없습니다." in no_result_text or not rows:
        return f"🔍 [{model_name}] 검색 결과가 없습니다."

    results = []
    for row in rows[:10]:  # 최대 10개만 표시
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

    if not model_name:
        return {"text": "모델명을 입력해주세요. 예: /ksel ktc-k501"}

    # 캐시에 있는지 먼저 확인
    if model_name in cache:
        cached_value = cache[model_name]
    else:
        cached_value = None

    try:
        # 3초 안에 응답 못 받으면 TimeoutError 발생
        result = await asyncio.wait_for(fetch_model_info(model_name), timeout=3.0)

        # 캐시에 저장 (최대 20개 유지)
        cache[model_name] = result
        if len(cache) > CACHE_LIMIT:
            cache.popitem(last=False)  # 가장 오래된 항목 제거

        return {"text": result}

    except asyncio.TimeoutError:
        if cached_value:
            return {"text": f"⚡ \n{cached_value}"}
        else:
            return {"text": f"⚠️ [{model_name}] 조회 중 응답이 지연되었습니다. 잠시 후 다시 시도해주세요."}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
