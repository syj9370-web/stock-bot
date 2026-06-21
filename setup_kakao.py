"""
카카오톡 설정 (처음 1번만 실행)
python setup_kakao.py
"""
import json, webbrowser, requests, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

REST_API_KEY  = os.getenv("KAKAO_REST_API_KEY", "")
CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")

if not REST_API_KEY:
    REST_API_KEY = input("카카오 REST API 키 입력: ").strip()

REDIRECT_URI = "http://localhost:8080"
code_box = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            code_box.append(params["code"][0])
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>✅ 인증 완료! 터미널을 확인하세요.</h2>".encode())

    def log_message(self, *args):
        pass  # 로그 억제

server = HTTPServer(("localhost", 8080), Handler)
t = threading.Thread(target=server.serve_forever)
t.daemon = True
t.start()

auth_url = (
    f"https://kauth.kakao.com/oauth/authorize"
    f"?client_id={REST_API_KEY}&redirect_uri={REDIRECT_URI}"
    f"&response_type=code&scope=talk_message"
)

print("\n브라우저가 열립니다 → 카카오 로그인 후 기다려주세요...")
webbrowser.open(auth_url)

# 코드 수신 대기 (최대 60초)
for _ in range(60):
    if code_box:
        break
    time.sleep(1)

server.shutdown()

if not code_box:
    print("❌ 시간 초과. 다시 실행해주세요.")
    exit(1)

code = code_box[0]
token_data = {
    "grant_type": "authorization_code",
    "client_id": REST_API_KEY,
    "redirect_uri": REDIRECT_URI,
    "code": code,
}
if CLIENT_SECRET:
    token_data["client_secret"] = CLIENT_SECRET

resp = requests.post("https://kauth.kakao.com/oauth/token", data=token_data)
data = resp.json()

if "access_token" not in data:
    print(f"\n❌ 실패: {data}")
else:
    Path("kakao_token.json").write_text(json.dumps({
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
    }))
    print("\n✅ 완료! 이제 recommend.py를 실행하면 카카오톡으로 받을 수 있어요.")
