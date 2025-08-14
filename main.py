import os
from fastapi import FastAPI, Request
import httpx
from bs4 import BeautifulSoup
import uvicorn

app = FastAPI()

# 전역 AsyncClient (비동기 연결 풀)
client = httpx.AsyncClient(
    timeout=5.0,
    limits=httpx.Limits(
        max_connections=10,      # 최대 연결 수
        max_keepalive_connections=5,  # Keep-Alive 유지 연결 수
        keepalive_expiry=30.0    # Keep-Alive 연결 유지 시간(초)
    )
)

@app.on_event("startup")
async def warmup():
    """
    서버 시작 시 예열 작업: 크레피아 사이트를 한 번 호출해서 연결 풀 초기화
    """
    try:
        search_url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"
        payload = {"searchKey": "03", "searchValue": "test", "currentPage": "1"}
        resp = await client.post(search_url, data=payload)
        if resp.status_code == 200:
            print("✅ 예열 완료 (크레피아 사이트 연결 성공)")
        else:
            print(f"⚠️ 예열 실패 (status: {resp.status_code})")
    except Exception as e:
        print(f"❌ 예열 중 오류: {e}")

@app.post("/ksel")
async def ksel_command(request: Request):
    data = await request.json()
    model_name = data.get("text", "").strip()

    if not model_name:
        return {"text": "모델명을 입력해주세요. 예: /ksel ktc-k501"}

    search_url = "https://www.crefia.or.kr/portal/store/cardTerminal/cardTerminalList.xx"
    payload = {
        "searchKey": "03",     # 모델명 조건검색
        "searchValue": model_name,
        "currentPage": "1"
    }

    response = await client.post(search_url, data=payload)

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    # "검색된 건이 없습니다." 문구 있는지 먼저 확인
    no_result_text = soup.get_text(strip=True)
    if "검색된 건이 없습니다." in no_result_text:
        return {"text": f"🔍 [{model_name}] 검색 결과가 없습니다."}

    if not rows:
        return {"text": f"🔍 [{model_name}] 검색 결과가 없습니다."}

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

    final_message = "\n\n".join(results)
    return {"text": final_message}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
