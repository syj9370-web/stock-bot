"""
GitHub Actions 클라우드 실행용 스크립트
- HTML 리포트를 report_latest.html 로 저장
- 카카오톡으로 리포트 링크 + 요약 전송
"""
import json, os, requests, shutil
from pathlib import Path
from datetime import datetime

# 환경변수에서 토큰 직접 로드 (클라우드 환경)
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
KAKAO_REST_API_KEY= os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_CLIENT_SECRET=os.environ.get("KAKAO_CLIENT_SECRET", "")
ACCESS_TOKEN      = os.environ.get("KAKAO_ACCESS_TOKEN", "")
REFRESH_TOKEN     = os.environ.get("KAKAO_REFRESH_TOKEN", "")

GITHUB_USER = "syj9370-web"
GITHUB_REPO = "stock-bot"
REPORT_URL  = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/report_latest.html"

def refresh_kakao_token():
    """액세스 토큰 갱신"""
    resp = requests.post("https://kauth.kakao.com/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "client_secret": KAKAO_CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
    })
    data = resp.json()
    return data.get("access_token", ACCESS_TOKEN)

def send_kakao(message: str, token: str):
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/x-www-form-urlencoded"}
    template = {
        "object_type": "text",
        "text": message,
        "link": {"web_url": REPORT_URL, "mobile_web_url": REPORT_URL},
        "button_title": "📊 리포트 보기"
    }
    resp = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                         headers=headers,
                         data={"template_object": json.dumps(template, ensure_ascii=False)})
    return resp.status_code == 200

# .env 없이 환경변수로 동작하도록 recommend.py의 함수 임포트
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

from recommend import scan, STOCKS, ETFS, get_sector_performance, ask_gemini, save_html

print("📊 주식 스캔 중...")
stocks = scan(STOCKS)
etfs   = scan(ETFS, is_etf=True)

if not stocks:
    print("❌ 분석 종목 없음"); exit(1)

top5    = stocks[:5]
top_etf = etfs[:2]
print(f"✅ {[s['name'] for s in top5]}")

print("📊 섹터 분석 중...")
sector_perf = get_sector_performance()

print("🤖 AI 분석 중...")
ai_text = ask_gemini(top5, top_etf)

print("📄 HTML 리포트 생성 중...")
html_path = save_html(ai_text, top5, top_etf, sector_perf)

# report_latest.html 로 복사
shutil.copy(html_path, "report_latest.html")
print(f"✅ report_latest.html 생성")

# 카카오톡 전송
token = refresh_kakao_token()
today = datetime.now().strftime("%Y년 %m월 %d일")
msg = f"📈 AI 주식 추천 TOP 5 ({today})\n\n"
for i, s in enumerate(top5, 1):
    msg += f"{i}위 {s['name']} {s['price']:,}원 ({s['change']:+.1f}%)\n"
msg += f"\n📊 리포트 링크 아래 버튼을 눌러주세요"

if send_kakao(msg, token):
    print("✅ 카카오톡 전송 완료!")
else:
    print("❌ 카카오톡 전송 실패")
