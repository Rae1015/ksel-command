from fastapi import FastAPI, Request
import httpx
from bs4 import BeautifulSoup
import time

app = FastAPI()

# 메모리 캐시 구조: { "모델명": (결과문자열, 저장시간) }
cache = {}
CACHE_DURATION = 3600  # 1시간(초)

@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    model_name = data.get("text", "").strip()

    if not model_name:
        return {"text": "모델명을 입력해주세요. 예: /ksel KTC-K501"}

    now = time.time()

    # 1. 캐시 확인
    if model_name in cache:
        cached_result, timestamp = cache[model_name]
        if now - timestamp < CACHE_DURATION:
            return {"text": f"{cached_result}"}

    # 2. 크레피아 사이트 요청
    search_url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"
    payload = {
        "searchKey": "03",   # 모델명으로 검색
        "searchValue": model_name,
        "currentPage": "1"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(search_url, data=payload)
            response.raise_for_status()
    except httpx.RequestError as e:
        return {"text": f"⚠️ 검색 중 오류가 발생했습니다.\n{str(e)}"}

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    if not rows:
        result = f"🔍 [{model_name}] 검색 결과가 없습니다."
        cache[model_name] = (result, now)  # 캐시에 저장
        return {"text": result}

    results = []
    for row in rows[:10]:  # 최대 10개 결과만
        cols = row.find_all("td")
        if len(cols) >= 8:
            cert_no = cols[2].text.strip()
            identifier = cols[3].text.strip().split()[0]
            model = cols[5].text.strip().split()[0]
            date_raw = cols[6].text.strip().split()
            cert_date = date_raw[0]
            exp_date = date_raw[1]

            results.append(
                f"[{cert_no}] {model}\n"
                f" - 식별번호 : {identifier}\n"
                f" - 인증일자 : {cert_date}\n"
                f" - 만료일자 : {exp_date}"
            )

    final_message = "\n\n".join(results)

    # 3. 캐시에 저장
    cache[model_name] = (final_message, now)

    return {"text": final_message}
