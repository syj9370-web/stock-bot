"""
주식 TOP 5 + ETF 추천봇
실행:  python recommend.py
자동:  python recommend.py --auto
"""

import json, os, re, time, webbrowser, logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 불필요한 로그 억제
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GLOG_minloglevel", "3")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("grpc").setLevel(logging.CRITICAL)

import requests
import yfinance as yf
from groq import Groq

GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
KAKAO_TOKEN_FILE = Path("kakao_token.json")

STOCKS = [
    # 반도체
    ("005930", "삼성전자",       "반도체"),
    ("000660", "SK하이닉스",     "반도체"),
    ("357780", "솔브레인",       "반도체소재"),
    ("036830", "솔브레인홀딩스", "반도체소재"),
    ("058470", "리노공업",       "반도체"),
    ("240810", "원익IPS",        "반도체장비"),
    ("403870", "HPSP",           "반도체장비"),
    # AI·IT
    ("035420", "NAVER",          "IT"),
    ("035720", "카카오",         "IT"),
    ("259960", "크래프톤",       "게임"),
    ("263750", "펄어비스",       "게임"),
    ("036570", "엔씨소프트",     "게임"),
    ("042700", "한미반도체",     "반도체장비"),
    # 방산
    ("012450", "한화에어로스페이스","방산"),
    ("047810", "한국항공우주",   "방산"),
    ("064350", "현대로템",       "방산"),
    ("241560", "두산밥캣",       "방산"),
    # 바이오·헬스
    ("145020", "휴젤",           "바이오"),
    ("196170", "알테오젠",       "바이오"),
    ("009540", "HD한국조선해양", "조선"),
    ("010140", "삼성중공업",     "조선"),
    ("042660", "한화오션",       "조선"),
    # 자동차
    ("005380", "현대차",         "자동차"),
    ("000270", "기아",           "자동차"),
    # 에너지·소재
    ("006400", "삼성SDI",        "배터리"),
    ("086520", "에코프로",       "배터리소재"),
    ("247540", "에코프로비엠",   "배터리소재"),
    ("051910", "LG화학",         "화학"),
    ("096770", "SK이노베이션",   "에너지"),
    # 금융
    ("105560", "KB금융",         "금융"),
    ("055550", "신한지주",       "금융"),
    ("086790", "하나금융지주",   "금융"),
    # 기타
    ("011200", "HMM",            "해운"),
    ("003670", "포스코홀딩스",   "철강"),
    ("066570", "LG전자",         "전자"),
]

# 산업별 시총 상위 종목 (산업 분석 탭용)
INDUSTRY_MAP = {
    # ── 반도체 ──────────────────────────────────────
    "반도체": [
        ("005930","삼성전자"),       ("000660","SK하이닉스"),
        ("042700","한미반도체"),     ("403870","HPSP"),
        ("058470","리노공업"),       ("240810","원익IPS"),
        ("357780","솔브레인"),       ("000990","DB하이텍"),
        ("036830","솔브레인홀딩스"), ("054620","APS홀딩스"),
    ],
    # ── IT·게임·플랫폼 ───────────────────────────────
    "IT·게임·플랫폼": [
        ("035420","NAVER"),        ("035720","카카오"),
        ("259960","크래프톤"),     ("036570","엔씨소프트"),
        ("263750","펄어비스"),     ("251270","넷마블"),
        ("293490","카카오게임즈"), ("112040","위메이드"),
        ("067160","아프리카TV"),
    ],
    # ── 방산 ────────────────────────────────────────
    "방산": [
        ("012450","한화에어로스페이스"), ("047810","한국항공우주"),
        ("064350","현대로템"),          ("272210","한화시스템"),
        ("079550","LIG넥스원"),         ("000880","한화"),
        ("267260","현대일렉트릭"),      ("241560","두산밥캣"),
    ],
    # ── 조선·해운 ────────────────────────────────────
    "조선·해운": [
        ("009540","HD한국조선해양"),  ("010140","삼성중공업"),
        ("042660","한화오션"),        ("010620","HD현대미포조선"),
        ("329180","HD현대중공업"),    ("011200","HMM"),
        ("028670","팬오션"),          ("005880","대한해운"),
        ("086280","현대글로비스"),    ("000120","CJ대한통운"),
    ],
    # ── 바이오·헬스 ──────────────────────────────────
    "바이오·헬스": [
        ("207940","삼성바이오로직스"), ("068270","셀트리온"),
        ("145020","휴젤"),             ("196170","알테오젠"),
        ("326030","SK바이오팜"),       ("214150","클래시스"),
        ("128940","한미약품"),         ("185750","종근당"),
        ("000020","동화약품"),         ("170900","동아에스티"),
    ],
    # ── 2차전지·소재 ─────────────────────────────────
    # 003670=포스코퓨처엠(양극재), 011790=SKC(동박·필름)
    "2차전지": [
        ("006400","삼성SDI"),      ("086520","에코프로"),
        ("247540","에코프로비엠"), ("096770","SK이노베이션"),
        ("003670","포스코퓨처엠"), ("066970","엘앤에프"),
        ("178920","PI첨단소재"),   ("011790","SKC"),
    ],
    # ── 자동차·부품 ──────────────────────────────────
    "자동차·부품": [
        ("005380","현대차"),      ("000270","기아"),
        ("012330","현대모비스"),  ("204320","HL만도"),
        ("073240","금호타이어"),  ("161390","한국타이어앤테크놀로지"),
        ("018880","한온시스템"),  ("014790","HL홀딩스"),
        ("011070","LG이노텍"),    ("007340","DN오토모티브"),
    ],
    # ── 금융·보험 ────────────────────────────────────
    "금융·보험": [
        ("105560","KB금융"),       ("055550","신한지주"),
        ("086790","하나금융지주"), ("024110","기업은행"),
        ("000810","삼성화재"),     ("032830","삼성생명"),
        ("088350","한화생명"),     ("139130","DGB금융지주"),
        ("071050","한국금융지주"), ("000060","메리츠화재"),
    ],
    # ── 철강·소재 ────────────────────────────────────
    "철강·소재": [
        ("005490","POSCO홀딩스"), ("004020","현대제철"),
        ("001230","동국제강"),    ("009730","코오롱인더"),
        ("002380","KCC"),         ("010060","OCI"),
        ("001440","대한전선"),
    ],
    # ── 화학·에너지 ──────────────────────────────────
    "화학·에너지": [
        ("051910","LG화학"),     ("011170","롯데케미칼"),
        ("009830","한화솔루션"), ("010950","S-Oil"),
        ("078930","GS"),         ("011780","금호석유"),
        ("015760","한국전력"),   ("036460","한국가스공사"),
    ],
    # ── 전자·통신 ────────────────────────────────────
    "전자·통신": [
        ("017670","SK텔레콤"),   ("030200","KT"),
        ("032640","LG유플러스"), ("053210","스카이라이프"),
        ("066570","LG전자"),     ("034220","LG디스플레이"),
        ("009150","삼성전기"),   ("018260","삼성SDS"),
    ],
    # ── 건설·인프라 ──────────────────────────────────
    "건설·인프라": [
        ("000720","현대건설"),       ("028260","삼성물산"),
        ("047040","대우건설"),       ("006360","GS건설"),
        ("034020","두산에너빌리티"), ("010120","LS ELECTRIC"),
        ("047050","포스코인터내셔널"),("003490","대한항공"),
    ],
    # ── 유통·소비재·식품 ─────────────────────────────
    "유통·소비재": [
        ("139480","이마트"),     ("023530","롯데쇼핑"),
        ("004170","신세계"),     ("069960","현대백화점"),
        ("097950","CJ제일제당"),("271560","오리온"),
        ("005300","롯데칠성"),  ("001680","대상"),
        ("383220","F&F"),        ("111770","영원무역"),
    ],
    # ── 엔터테인먼트·미디어 ──────────────────────────
    "엔터·미디어": [
        ("352820","하이브"),         ("041510","에스엠"),
        ("035900","JYP Ent."),       ("122870","YG엔터테인먼트"),
        ("035760","CJ ENM"),         ("036420","제이콘텐트리"),
        ("034120","SBS"),            ("079160","CJ CGV"),
        ("030000","제일기획"),
    ],
}

ETFS = [
    ("069500", "KODEX 200",       "국내시장대표"),
    ("091160", "KODEX 반도체",    "반도체"),
    ("229200", "KODEX 코스닥150", "코스닥"),
    ("305720", "KODEX 2차전지",   "배터리"),
    ("139220", "TIGER 200IT",     "IT섹터"),
]

# 섹터 강도 판단용 ETF (등락률 기반)
SECTOR_ETFS = [
    ("091160", "반도체"),
    ("139220", "IT"),
    ("091220", "금융"),
    ("305720", "2차전지"),
    ("143860", "헬스케어"),
    ("117460", "화학"),
    ("091180", "자동차"),
    ("117730", "철강"),
    ("069500", "코스피200"),
    ("229200", "코스닥150"),
]


def _safe_float(v) -> float:
    """문자열/None/숫자 → float 안전 변환"""
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0.0


def calc_support_resistance(closes: list) -> tuple:
    """지지선·저항선 계산 (최근 60일 피봇 기준)"""
    n = min(60, len(closes))
    data = closes[-n:]
    current = data[-1]
    supports, resistances = [], []

    # 피봇 로우/하이 탐색 (window=3)
    for i in range(3, len(data) - 3):
        is_low  = all(data[i] <= data[i-j] for j in range(1, 4)) and all(data[i] <= data[i+j] for j in range(1, 4))
        is_high = all(data[i] >= data[i-j] for j in range(1, 4)) and all(data[i] >= data[i+j] for j in range(1, 4))
        if is_low  and data[i] < current * 1.05:
            supports.append(data[i])
        if is_high and data[i] > current * 0.95:
            resistances.append(data[i])

    # 현재가 아래 최근 지지선, 현재가 위 최근 저항선
    sup_candidates = [x for x in supports if x < current]
    res_candidates = [x for x in resistances if x > current]

    support    = max(sup_candidates) if sup_candidates else min(data)
    resistance = min(res_candidates) if res_candidates else max(data)
    return int(support), int(resistance)


def calc_volume_profile(closes: list, volumes: list) -> tuple:
    """매물대 계산 — 거래량 집중 가격대 (POC: Point of Control)"""
    n = min(60, len(closes))
    c = closes[-n:]
    v = volumes[-n:]
    if not c:
        return None, None
    pmin, pmax = min(c), max(c)
    if pmin == pmax:
        return pmin, pmax

    bins = 12
    step = (pmax - pmin) / bins
    vol_bins = [0.0] * bins
    for price, vol in zip(c, v):
        idx = min(int((price - pmin) / step), bins - 1)
        vol_bins[idx] += vol

    peak = vol_bins.index(max(vol_bins))
    poc_lo = int(pmin + peak * step)
    poc_hi = int(pmin + (peak + 1) * step)
    return poc_lo, poc_hi


def fetch_chart_data(code: str) -> dict | None:
    """차트 데이터(종가·거래량) 수집 — 산업 분석 탭 전용"""
    try:
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=120&requestType=0"
        r = requests.get(url, timeout=8, headers=NAVER_HEADERS)
        r.encoding = "euc-kr"
        closes, volumes = [], []
        for line in r.text.split("\n"):
            if "<item" not in line:
                continue
            vals = re.findall(r'data="([^"]+)"', line)
            if vals:
                parts = vals[0].split("|")
                if len(parts) >= 5:
                    try:
                        closes.append(int(parts[3]))
                        volumes.append(int(parts[4]))
                    except Exception:
                        pass
        return {"closes": closes, "volumes": volumes} if closes else None
    except Exception:
        return None


def scan_industry() -> dict:
    """산업별 분석 데이터 수집"""
    result = {}
    for industry, stocks in INDUSTRY_MAP.items():
        rows = []
        for code, name in stocks:
            print(f"  [산업분석] {name}...", end="\r")
            # 현재가
            nv = {"price": None, "change": 0.0, "nxt_price": None, "nxt_change": 0.0}
            try:
                r1 = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic",
                                  timeout=5, headers=NAVER_HEADERS)
                b = r1.json()
                p = str(b.get("closePrice", "")).replace(",", "")
                c = str(b.get("fluctuationsRatio", "")).replace(",", "")
                if p and p != "0":
                    nv["price"]  = int(p)
                    nv["change"] = float(c) if c else 0.0
                over = b.get("overMarketPriceInfo")
                if isinstance(over, dict):
                    np2 = str(over.get("closePrice", "")).replace(",", "")
                    nc2 = str(over.get("fluctuationsRatio", "")).replace(",", "")
                    if np2 and np2 != "0":
                        nv["nxt_price"]  = int(np2)
                        nv["nxt_change"] = float(nc2) if nc2 else 0.0
            except Exception:
                pass

            # 차트 데이터
            chart = fetch_chart_data(code)
            rsi_val, support, resistance, poc_lo, poc_hi = None, None, None, None, None
            if chart and len(chart["closes"]) >= 20:
                closes = chart["closes"]
                volumes = chart["volumes"]
                # RSI
                rsi_val = calc_rsi(closes)
                # 지지·저항
                support, resistance = calc_support_resistance(closes)
                # 매물대
                poc_lo, poc_hi = calc_volume_profile(closes, volumes)

            rows.append({
                "code": code, "name": name,
                "price": nv["price"], "change": nv["change"],
                "nxt_price": nv["nxt_price"], "nxt_change": nv["nxt_change"],
                "rsi": rsi_val, "support": support, "resistance": resistance,
                "poc_lo": poc_lo, "poc_hi": poc_hi,
            })
            time.sleep(0.15)
        result[industry] = rows
    return result

def get_sector_performance() -> list:
    """섹터 ETF 실제 등락률로 주도 섹터 산출"""
    result = []
    for code, sector in SECTOR_ETFS:
        try:
            r = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic",
                             timeout=5, headers=NAVER_HEADERS)
            d = r.json()
            chg = _safe_float(str(d.get("fluctuationsRatio", "0")).replace(",", ""))
            price = str(d.get("closePrice", "0")).replace(",", "")
            result.append({"sector": sector, "code": code, "change": chg, "price": int(price) if price else 0})
        except Exception:
            pass
        time.sleep(0.1)
    result.sort(key=lambda x: x["change"], reverse=True)
    return result

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    "Referer": "https://m.stock.naver.com/",
}

def get_naver_data(code: str) -> dict:
    """네이버 증권에서 현재가 + PER/PBR 한번에 조회"""
    result = {"price": None, "change": None, "per": 0, "per_ind": 0, "pbr": 0, "nxt_price": None, "nxt_change": None}
    try:
        # 1) /basic 항상 먼저 호출 → NXT 야간 종가 + 가격 기본값
        r1 = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic",
                          timeout=6, headers=NAVER_HEADERS)
        b = r1.json()
        raw_price  = str(b.get("closePrice", "")).replace(",", "")
        raw_change = str(b.get("fluctuationsRatio", "")).replace(",", "")
        if raw_price and raw_price != "0":
            result["price"]  = int(raw_price)
            result["change"] = float(raw_change) if raw_change else 0.0

        # NXT 야간 시간외 종가 (overMarketPriceInfo)
        over = b.get("overMarketPriceInfo")
        if isinstance(over, dict):
            nxt_p = str(over.get("closePrice", "")).replace(",", "")
            nxt_c = str(over.get("fluctuationsRatio", "")).replace(",", "")
            if nxt_p and nxt_p not in ("0", ""):
                result["nxt_price"]  = int(nxt_p)
                result["nxt_change"] = float(nxt_c) if nxt_c else 0.0

        # 2) 장중이면 실시간 현재가로 덮어쓰기 (실패해도 무시)
        try:
            r_rt = requests.get(
                f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}",
                timeout=4, headers=NAVER_HEADERS)
            rt = r_rt.json().get("datas", [{}])[0]
            rt_price = str(rt.get("closePrice", rt.get("currentPrice", ""))).replace(",", "")
            rt_chg   = str(rt.get("fluctuationsRatio", "")).replace(",", "")
            if rt_price and rt_price != "0":
                result["price"]  = int(rt_price)
                result["change"] = float(rt_chg) if rt_chg else 0.0
        except Exception:
            pass
    except Exception:
        pass
    try:
        # 2) PER/PBR: Naver Finance 메인 페이지 HTML 스크래핑
        r2 = requests.get(f"https://finance.naver.com/item/main.nhn?code={code}",
                          timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r2.encoding = "euc-kr"
        html = r2.text
        # PER(배) 바로 다음 <td> 안의 숫자 추출
        per_m = re.search(
            r'PER[^<]*</strong></th>[\s\S]*?<td[^>]*>[\s\t\n]*([\d,\.]+)[\s\S]*?<td[^>]*>[\s\t\n]*([\d,\.]+)', html)
        pbr_m = re.search(
            r'PBR[^<]*</strong></th>[\s\S]*?<td[^>]*>[\s\t\n]*([\d,\.]+)[\s\S]*?<td[^>]*>[\s\t\n]*([\d,\.]+)', html)
        if per_m:
            result["per"]     = round(_safe_float(per_m.group(1).replace(",", "")), 1)
            result["per_ind"] = round(_safe_float(per_m.group(2).replace(",", "")), 1)
        if pbr_m:
            result["pbr"] = round(_safe_float(pbr_m.group(1).replace(",", "")), 2)
    except Exception:
        pass
    return result


def get_stock_data(code: str) -> dict | None:
    """네이버 차트 API로 OHLCV + 현재가 + PER 조회 (yfinance 대체)"""
    try:
        # 1) 120일치 일봉 차트 (XML 형식)
        chart_url = (
            f"https://fchart.stock.naver.com/sise.nhn"
            f"?symbol={code}&timeframe=day&count=120&requestType=0"
        )
        r = requests.get(chart_url, timeout=8, headers=NAVER_HEADERS)
        r.encoding = "euc-kr"
        lines = [l for l in r.text.split("\n") if "<item" in l]
        if len(lines) < 20:
            return None

        closes, volumes = [], []
        for line in lines:
            vals = re.findall(r'data="([^"]+)"', line)
            if not vals:
                continue
            parts = vals[0].split("|")
            if len(parts) >= 5:
                closes.append(int(parts[3]))   # close
                volumes.append(int(parts[4]))  # volume

        if len(closes) < 20:
            return None

        # 2) 현재가·등락률 + PER/PBR
        naver = get_naver_data(code)
        price  = naver["price"]  if naver["price"]  else closes[-1]
        change = naver["change"] if naver["change"] is not None else \
                 round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
        closes[-1] = price  # 마지막 값을 네이버 현재가로 교체

        return {
            "closes": closes, "volumes": volumes,
            "price": price, "change": change,
            "per": naver["per"], "per_ind": naver["per_ind"], "pbr": naver["pbr"],
            "nxt_price": naver.get("nxt_price"), "nxt_change": naver.get("nxt_change"),
        }
    except Exception as e:
        print(f"\n[ERR {code}] {e}")
        return None


def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return 50.0
    ch = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    ag = sum(c for c in ch[-period:] if c > 0) / period
    al = sum(-c for c in ch[-period:] if c < 0) / period
    return round(100 - 100 / (1 + ag / al), 1) if al else 100.0

def ma(closes, n):
    return round(sum(closes[-n:]) / n, 0) if len(closes) >= n else None

def calc_score(closes, volumes):
    score, signals = 50, []
    rsi = calc_rsi(closes)
    cur = closes[-1]
    ma5, ma20, ma30, ma60 = ma(closes,5), ma(closes,20), ma(closes,30), ma(closes,60)

    if rsi < 35:   score += 20; signals.append(f"RSI 과매도({rsi})")
    elif rsi < 48: score += 10; signals.append(f"RSI 저점({rsi})")
    elif rsi > 68: score -= 15

    if ma5 and ma20 and ma60:
        if cur > ma5 > ma20 > ma60: score += 15; signals.append("이평 정배열")
        elif cur > ma20 > ma60:     score += 8;  signals.append("MA20>60 정배열")
        elif cur < ma5 < ma20:      score -= 10

    if ma30 and abs(cur - ma30) / ma30 < 0.03:
        score += 8; signals.append("30일선 지지")

    if len(volumes) >= 6:
        avg = sum(volumes[-6:-1]) / 5
        r = volumes[-1] / avg if avg else 1
        if r >= 3:   score += 15; signals.append(f"거래량 {r:.1f}x 급등")
        elif r >= 2: score += 8;  signals.append(f"거래량 {r:.1f}x 증가")

    if len(closes) >= 5:
        t = (closes[-1] - closes[-5]) / closes[-5] * 100
        if 1 < t < 12: score += 5; signals.append(f"5일 +{t:.1f}%")
        elif t < -10:  score -= 10

    return max(0, min(100, score)), signals, rsi, ma20, ma30, ma60


def scan(universe, is_etf=False):
    results = []
    for code, name, sector in universe:
        try:
            d = get_stock_data(code)
            if not d or len(d["closes"]) < 20: continue
            score, signals, rsi, ma20, ma30, ma60 = calc_score(d["closes"], d["volumes"])
            results.append({
                "code": code, "name": name, "sector": sector,
                "price": d["price"], "change": d["change"],
                "score": score, "signals": signals, "rsi": rsi,
                "ma20": ma20, "ma30": ma30, "ma60": ma60,
                "per": d["per"], "per_ind": d["per_ind"], "pbr": d["pbr"],
                "nxt_price": d.get("nxt_price"), "nxt_change": d.get("nxt_change"),
                "closes5": d["closes"][-5:], "is_etf": is_etf,
            })
            print(".", end="", flush=True)
        except Exception:
            print("x", end="", flush=True)
        time.sleep(0.15)
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def ask_gemini(stocks, etfs):
    if not GROQ_API_KEY:
        print("\n⚠️  GROQ_API_KEY 없음")
        return _fallback(stocks, etfs)
    try:
        client = Groq(api_key=GROQ_API_KEY)
        today = datetime.now().strftime("%Y년 %m월 %d일")
        sectors = {}
        for s in stocks: sectors.setdefault(s["sector"], []).append(s["name"])

        stock_data = "\n".join(
            f"{i+1}. {s['name']}({s['code']}) | 현재가:{s['price']:,}원 | 등락:{s['change']:+.1f}% | "
            f"RSI:{s['rsi']} | MA20:{int(s['ma20']) if s['ma20'] else 'N/A'}원 | MA60:{int(s['ma60']) if s['ma60'] else 'N/A'}원 | "
            f"PER:{s['per'] if s['per'] else 'N/A'}배 | PBR:{s['pbr'] if s['pbr'] else 'N/A'}배 | "
            f"기술점수:{s['score']}점 | 신호:{', '.join(s['signals']) if s['signals'] else '없음'}"
            for i, s in enumerate(stocks)
        )
        etf_data = "\n".join(
            f"{e['name']} | {e['price']:,}원 | {e['change']:+.1f}% | {e['sector']}"
            for e in etfs
        )

        prompt = f"""당신은 20년 경력의 한국 주식 전문 애널리스트입니다. 오늘({today}) 단기 10% 이상 수익을 목표로 종목을 추천해주세요.

[분석 대상 종목 (기술적 점수 상위)]
{stock_data}

[ETF 현황]
{etf_data}

[선정 기준 - 반드시 준수]
- RSI 30~60 구간 (과매도 탈출 또는 중립 구간 진입 중인 종목 우선)
- 이동평균선 정배열(MA5>MA20>MA60) 또는 골든크로스 임박 종목
- 거래량 급증(평균 대비 2배 이상) 동반 시 강력 매수 신호
- PER이 업종 평균 대비 저평가된 종목 우선
- 최근 5일 상승 모멘텀이 살아있는 종목

아래 형식으로 정확히 작성하세요 (다른 말 없이 형식만):

[시장 분석]
오늘 시장의 핵심 흐름과 주도 섹터를 3문장으로 서술.

[주식 추천 TOP 5]
1위: 종목명 (섹터)
현재가: X원 | 목표가: X원 | 손절가: X원 | 예상수익: +X% | 투자기간: X주
매수근거: RSI·이평선·거래량·PER 수치를 직접 인용하며 3문장으로 설명. 왜 10% 수익이 가능한지 구체적으로.
리스크: 이 종목의 핵심 하락 리스크 1문장.

2위: 종목명 (섹터)
현재가: X원 | 목표가: X원 | 손절가: X원 | 예상수익: +X% | 투자기간: X주
매수근거: (동일 형식)
리스크: (1문장)

3위~5위도 동일 형식.

[ETF 추천 TOP 2]
1위: ETF명 | 목표가: X원 | 손절가: X원 | 추천이유: (2문장)
2위: ETF명 | 목표가: X원 | 손절가: X원 | 추천이유: (2문장)

[오늘의 한줄 전략]
오늘 가장 중요한 매매 전략 한 문장."""

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "당신은 한국 주식시장 전문 애널리스트입니다. 반드시 한국어로만 답변하세요. 영어, 터키어 등 다른 언어는 절대 사용하지 마세요. '펀더멘털'은 '펀더멘털'로, 'temel'같은 외국어는 사용 금지입니다. 수치 기반의 정확하고 전문적인 분석을 제공합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2500,
        )
        text = resp.choices[0].message.content
        # 간혹 다국어 혼용 단어 후처리 (temel = 터키어 '펀더멘털')
        text = re.sub(r'\btemel\b', '펀더멘털', text, flags=re.IGNORECASE)
        return text
    except Exception as e:
        print(f"\nGroq 오류: {e}")
        return _fallback(stocks, etfs)


def _fallback(stocks, etfs):
    """Gemini 없을 때 기술 지표 기반 자동 분석 생성"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    # 섹터 집계
    sec_scores = {}
    for s in stocks:
        sec_scores.setdefault(s["sector"], []).append(s["score"])
    top_sector = max(sec_scores, key=lambda k: sum(sec_scores[k])/len(sec_scores[k]))

    lines = [f"[시장 분석]\n"
             f"오늘 기술적 점수 기준 주도 섹터는 {top_sector}입니다. "
             f"상위 종목들의 평균 기술 점수는 {round(sum(s['score'] for s in stocks[:5])/5)}점으로 "
             f"{'매수 우위' if sum(s['score'] for s in stocks[:5])/5 >= 60 else '관망 구간'}입니다. "
             f"RSI 과매도 구간 진입 종목 위주로 단기 반등 가능성에 주목하세요.\n",
             "[주식 추천 TOP 5]"]

    for i, s in enumerate(stocks[:5], 1):
        target = int(s["price"] * 1.07)
        stop   = int(s["price"] * 0.95)
        rsi_comment = "과매도 반등 기대" if s["rsi"] < 35 else "저점 매수 구간" if s["rsi"] < 48 else "중립"
        ma_comment  = "이평선 정배열" if s["ma20"] and s["price"] > s["ma20"] else "이평선 하방"
        lines.append(
            f"{i}위: {s['name']} ({s['sector']})\n"
            f"현재가: {s['price']:,}원 | 목표가: {target:,}원 | 손절가: {stop:,}원 | 예상수익: +7%\n"
            f"PER {s['per'] if s['per'] else 'N/A'}배 / RSI {s['rsi']} / "
            f"MA20 {int(s['ma20']):,}원\n" if s['ma20'] else
            f"PER {s['per'] if s['per'] else 'N/A'}배 / RSI {s['rsi']}\n"
            f"매수근거: 기술점수 {s['score']}점. {rsi_comment}, {ma_comment}. "
            f"주요 신호: {', '.join(s['signals'][:3]) if s['signals'] else '없음'}.\n"
            f"리스크: 단기 변동성 주의, 손절가 {stop:,}원 엄수.\n"
        )

    lines.append("[ETF 추천 TOP 2]")
    for i, e in enumerate(etfs[:2], 1):
        lines.append(f"{i}위: {e['name']} | 추천이유: {e['sector']} 섹터 대표 ETF. "
                     f"기술점수 {e['score']}점, 개별 종목 대비 분산 투자 효과.\n")

    lines.append(f"[오늘의 한줄 전략]\n{top_sector} 섹터 중심, RSI 저점 종목 분할 매수 전략 권장.")
    return "\n".join(lines)


def save_html(ai_text: str, stocks: list, etfs: list, sector_perf: list = [],
              industry_data: dict = None) -> Path:
    day_map = {"Mon":"월","Tue":"화","Wed":"수","Thu":"목","Fri":"금","Sat":"토","Sun":"일"}
    raw_today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    today = day_map.get(datetime.now().strftime("%a"), datetime.now().strftime("%a")).join(raw_today.rsplit(datetime.now().strftime("%a"), 1))
    today = datetime.now().strftime(f"%Y년 %m월 %d일 ({day_map.get(datetime.now().strftime('%a'), '')})")
    date_str  = datetime.now().strftime("%Y%m%d_%H%M")
    now_str   = datetime.now().strftime("%H:%M")

    # AI 텍스트에서 종목별 분석 파싱 (종목명 기준 매핑)
    stock_names = [s["name"] for s in stocks[:5]]
    ai_sections = {}   # {종목명: 분석텍스트}
    current_name = None
    current_lines = []
    # ETF/전략 섹션 시작 시 종목 파싱 종료
    STOP_PATTERNS = (r'^\[ETF', r'^\[오늘의', r'^ETF 추천', r'^오늘의 한줄')
    for line in ai_text.split("\n"):
        stripped = line.strip()
        # 섹션 구분자 만나면 현재 종목 저장 후 파싱 종료
        if any(re.match(p, stripped) for p in STOP_PATTERNS):
            if current_name:
                ai_sections[current_name] = "\n".join(current_lines).strip()
            current_name = None
            current_lines = []
            break
        # "N위: 종목명" 패턴 감지
        m = re.match(r'^\d위[:：]\s*(.+)', stripped)
        if m:
            header = m.group(1)
            matched = next((n for n in stock_names if n in header), None)
            if matched:
                if current_name:
                    ai_sections[current_name] = "\n".join(current_lines).strip()
                current_name = matched
                current_lines = [stripped]
                continue
        if current_name:
            current_lines.append(stripped)
    if current_name:
        ai_sections[current_name] = "\n".join(current_lines).strip()

    # 시장분석 추출
    market_m = re.search(r'\[시장 분석\]([\s\S]*?)(?=\[|$)', ai_text)
    market_txt = market_m.group(1).strip() if market_m else ""
    strategy_m = re.search(r'\[오늘의 한줄 전략\]([\s\S]*?)$', ai_text)
    strategy_txt = strategy_m.group(1).strip() if strategy_m else ""
    # ETF 분석 추출
    etf_ai_m = re.search(r'\[ETF 추천 TOP\s*\d*\]([\s\S]*?)(?=\[오늘의|$)', ai_text)
    etf_ai_raw = etf_ai_m.group(1).strip() if etf_ai_m else ""
    # ETF별 분석 파싱 (1위/2위 기준)
    etf_ai = {}
    for i, e in enumerate(etfs[:2], 1):
        m = re.search(rf'{i}위[^{chr(10)}]*{re.escape(e["name"])}([\s\S]*?)(?=\d위:|$)', etf_ai_raw)
        if not m:
            m = re.search(rf'{i}위:([\s\S]*?)(?=\d위:|$)', etf_ai_raw)
        etf_ai[e["name"]] = m.group(1).strip() if m else ""

    # 종목 아이템 HTML
    items = ""
    for i, s in enumerate(stocks[:5]):
        target   = int(s["price"] * 1.07)
        stop     = int(s["price"] * 0.95)
        per_str  = f"{s['per']}배" if s["per"] else "N/A"
        per_ind  = f" (업종 {s['per_ind']}배)" if s.get("per_ind") else ""
        chg_cls  = "pos" if s["change"] >= 0 else "neg"
        chg_sign = "▲" if s["change"] >= 0 else "▼"
        hashtags = " ".join(f'<span class="tag">#{sig.replace(" ","")}</span>' for sig in s["signals"][:4])
        # AI 분석 텍스트 (해당 종목 파트)
        ai_part  = ai_sections.get(s["name"], "")
        # 매수근거 줄만 추출
        invest_lines = []
        for ln in ai_part.split("\n"):
            ln = ln.strip()
            if ln and not re.match(r'\d위[:：]', ln):
                invest_lines.append(ln)
        invest_html = "<br>".join(invest_lines) if invest_lines else f"기술점수 {s['score']}점 · RSI {s['rsi']} · 신호: {', '.join(s['signals'][:3])}"

        items += f"""
  <div class="item">
    <div class="item-header">
      <div class="left">
        <span class="rank-num">{i+1}</span>
        <div>
          <div class="sname">{s['name']} <span class="scode">{s['code']}</span></div>
          <div class="ssector">{s['sector']}</div>
        </div>
      </div>
      <div class="right">
        <div class="sprice" id="price-{s['code']}">{s['price']:,}원</div>
        <div class="schange {chg_cls}" id="change-{s['code']}">{chg_sign} {abs(s['change']):.2f}%</div>
        {f'<div class="nxt-price">NXT {s["nxt_price"]:,}원 <span class="{"pos" if s["nxt_change"]>=0 else "neg"}">{"▲" if s["nxt_change"]>=0 else "▼"}{abs(s["nxt_change"]):.2f}%</span></div>' if s.get("nxt_price") else ""}
      </div>
    </div>
    <div class="tags">{hashtags}</div>
    <div class="kpi-row">
      <div class="kpi"><span class="kl">목표가</span><span class="kv target">{target:,}원</span></div>
      <div class="kpi"><span class="kl">손절가</span><span class="kv stop">{stop:,}원</span></div>
      <div class="kpi"><span class="kl">PER</span><span class="kv">{per_str}<small class="ind">{per_ind}</small></span></div>
      <div class="kpi"><span class="kl">RSI</span><span class="kv">{s['rsi']}</span></div>
      <div class="kpi"><span class="kl">MA20</span><span class="kv">{f"{int(s['ma20']):,}" if s['ma20'] else "N/A"}</span></div>
      <div class="kpi"><span class="kl">MA60</span><span class="kv">{f"{int(s['ma60']):,}" if s['ma60'] else "N/A"}</span></div>
    </div>
    <div class="invest-box">
      <div class="invest-title">[투자포인트]</div>
      <div class="invest-body">{invest_html}</div>
    </div>
  </div>"""

    # ETF
    etf_items = ""
    for e in etfs[:2]:
        chg_cls  = "pos" if e["change"] >= 0 else "neg"
        chg_sign = "▲" if e["change"] >= 0 else "▼"
        ai_comment = etf_ai.get(e["name"], "")
        etf_items += f"""
  <div class="item">
    <div class="item-header">
      <div class="left">
        <div>
          <div class="sname">{e['name']} <span class="scode">{e['code']}</span></div>
          <div class="ssector">{e['sector']}</div>
        </div>
      </div>
      <div class="right">
        <div class="sprice">{e['price']:,}원</div>
        <div class="schange {chg_cls}">{chg_sign} {abs(e['change']):.2f}%</div>
      </div>
    </div>
    {f'<div class="invest-box"><div class="invest-title">[추천이유]</div><div class="invest-body">{ai_comment}</div></div>' if ai_comment else ""}
  </div>"""

    # 섹터 ETF 등락률 바
    sector_html = ""
    for sec in sector_perf:
        chg = sec["change"]
        color = "#e5341a" if chg >= 0 else "#1a73e8"
        bar_w = min(abs(chg) * 15, 100)  # 최대 100%
        sign = "▲" if chg >= 0 else "▼"
        sector_html += f"""
  <div class="sec-row">
    <span class="sec-name">{sec['sector']}</span>
    <div class="sec-bar-wrap">
      <div class="sec-bar" style="width:{bar_w}%;background:{color}"></div>
    </div>
    <span class="sec-chg" style="color:{color}">{sign} {abs(chg):.2f}%</span>
  </div>"""

    codes_json = json.dumps({s["code"]: s["code"]+".KS" for s in stocks[:5]})

    # 산업별 분석 탭 HTML 생성
    industry_tab_html = ""
    if industry_data:
        ind_blocks = ""
        for ind_name, rows in industry_data.items():
            ind_rows = ""
            for row in rows:
                p = row.get("price")
                chg = row.get("change", 0)
                rsi = row.get("rsi")
                sup = row.get("support")
                res = row.get("resistance")
                poc_lo = row.get("poc_lo")
                poc_hi = row.get("poc_hi")
                nxt_p  = row.get("nxt_price")
                nxt_c  = row.get("nxt_change", 0)

                price_str  = f"{p:,}원" if p else "-"
                chg_cls    = "pos" if chg >= 0 else "neg"
                chg_str    = f"{'▲' if chg>=0 else '▼'}{abs(chg):.2f}%"

                rsi_color  = ("#e5341a" if rsi is not None and rsi >= 70
                              else "#1a73e8" if rsi is not None and rsi <= 30
                              else "#3b82f6")
                rsi_str    = f"{rsi:.1f}" if rsi is not None else "-"
                rsi_pct    = f"{min(max(rsi,0),100):.1f}%" if rsi is not None else "50%"

                sup_str    = f"{sup:,}" if sup else "-"
                res_str    = f"{res:,}" if res else "-"
                poc_str    = f"{poc_lo:,}~{poc_hi:,}" if poc_lo else "-"

                nxt_html = ""
                if nxt_p:
                    nxt_cls = "pos" if nxt_c >= 0 else "neg"
                    nxt_arr = "▲" if nxt_c >= 0 else "▼"
                    nxt_html = f'<span class="ind-nxt">NXT {nxt_p:,} <span class="{nxt_cls}">{nxt_arr}{abs(nxt_c):.2f}%</span></span>'

                ind_rows += f"""
<div class="ind-row">
  <div class="ind-name">
    <span class="ind-sname">{row['name']}</span>
    <span class="ind-code">{row['code']}</span>
  </div>
  <div class="ind-price-col">
    <span class="ind-price">{price_str}</span>
    <span class="ind-chg {chg_cls}">{chg_str}</span>
    {nxt_html}
  </div>
  <div class="ind-rsi-col">
    <div class="rsi-label-row">
      <span class="rsi-label">RSI</span>
      <span class="rsi-val" style="color:{rsi_color}">{rsi_str}</span>
    </div>
    <div class="rsi-bar-bg">
      <div class="rsi-bar" style="width:{rsi_pct};background:{rsi_color}"></div>
      <div class="rsi-mark30"></div>
      <div class="rsi-mark70"></div>
    </div>
  </div>
  <div class="ind-levels">
    <div class="level-row"><span class="lk">매물대</span><span class="lv poc">{poc_str}</span></div>
    <div class="level-row"><span class="lk">지지</span><span class="lv sup">{sup_str}</span></div>
    <div class="level-row"><span class="lk">저항</span><span class="lv res">{res_str}</span></div>
  </div>
</div>"""
            ind_blocks += f"""
<div class="ind-section">
  <div class="ind-section-title">{ind_name}</div>
  {ind_rows}
</div>"""
        industry_tab_html = ind_blocks

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 종목추천 {today}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;background:#f5f6f8;color:#111;min-height:100vh;max-width:680px;margin:0 auto}}
.topbar{{background:#fff;padding:.9rem 1rem;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #eee;position:sticky;top:0;z-index:10}}
.topbar-title{{font-size:1rem;font-weight:800;color:#111}}
.topbar-date{{font-size:.8rem;color:#888}}
/* 탭 */
.tab-nav{{background:#fff;display:flex;border-bottom:2px solid #eee;position:sticky;top:49px;z-index:9}}
.tab-btn{{flex:1;padding:.65rem .5rem;font-size:.85rem;font-weight:600;color:#999;border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:.2s}}
.tab-btn.active{{color:#111;border-bottom:2px solid #111}}
.tab-panel{{display:none}}.tab-panel.active{{display:block}}
/* 공통 */
.section-label{{font-size:.72rem;font-weight:700;color:#888;letter-spacing:.08em;text-transform:uppercase;padding:.9rem 1rem .4rem}}
.market-box{{background:#fff;margin:.5rem .75rem;border-radius:12px;padding:1rem 1.1rem;font-size:.88rem;line-height:1.7;color:#333;border-left:3px solid #3b82f6}}
.strategy-box{{background:#fffbeb;margin:.5rem .75rem;border-radius:12px;padding:.9rem 1.1rem;font-size:.88rem;color:#92400e;border-left:3px solid #f59e0b}}
.item{{background:#fff;margin:.5rem .75rem;border-radius:14px;padding:1.1rem;border:1px solid #eee}}
.item-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.6rem}}
.left{{display:flex;align-items:flex-start;gap:.6rem}}
.rank-num{{width:26px;height:26px;border-radius:50%;background:#111;color:#fff;font-size:.78rem;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px}}
.sname{{font-size:1.05rem;font-weight:800;color:#111}}
.scode{{font-size:.78rem;font-weight:400;color:#aaa;margin-left:4px}}
.ssector{{font-size:.76rem;color:#888;margin-top:2px}}
.right{{text-align:right}}
.sprice{{font-size:1.05rem;font-weight:700}}
.schange{{font-size:.82rem;font-weight:600;margin-top:2px}}
.pos{{color:#e5341a}}.neg{{color:#1a73e8}}
.tags{{display:flex;flex-wrap:wrap;gap:.3rem;margin:.5rem 0 .7rem}}
.tag{{background:#f0f4ff;color:#3b5bdb;padding:3px 9px;border-radius:99px;font-size:.72rem;font-weight:500}}
.kpi-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;background:#f8f9fa;border-radius:10px;padding:.7rem .8rem;margin-bottom:.8rem}}
.kpi{{display:flex;flex-direction:column;gap:2px}}
.kl{{font-size:.63rem;color:#999}}
.kv{{font-size:.88rem;font-weight:600;color:#111}}
.kv.target{{color:#e5341a}}.kv.stop{{color:#1a73e8}}
.ind{{font-size:.65rem;color:#999;font-weight:400}}
.invest-box{{border-top:1px solid #f0f0f0;padding-top:.75rem}}
.invest-title{{font-size:.82rem;font-weight:800;color:#333;margin-bottom:.35rem}}
.invest-body{{font-size:.84rem;line-height:1.75;color:#444}}
.etf-item{{background:#fff;margin:.5rem .75rem;border-radius:12px;padding:.9rem 1.1rem;border:1px solid #eee}}
.etf-left{{}}
.footer{{text-align:center;font-size:.72rem;color:#bbb;padding:1.5rem 1rem 2rem;}}
.nxt-price{{font-size:.72rem;color:#888;margin-top:2px;text-align:right}}
.update-time{{font-size:.7rem;color:#bbb;text-align:center;padding:.3rem}}
.sec-row{{display:flex;align-items:center;gap:.6rem;padding:.3rem 0}}
.sec-name{{width:72px;font-size:.78rem;color:#555;text-align:right;flex-shrink:0}}
.sec-bar-wrap{{flex:1;background:#eee;border-radius:99px;height:7px}}
.sec-bar{{height:7px;border-radius:99px;transition:width .4s}}
.sec-chg{{width:70px;font-size:.78rem;font-weight:600;text-align:right;flex-shrink:0}}
.sector-wrap{{background:#fff;margin:.5rem .75rem;border-radius:14px;padding:.9rem 1.1rem;border:1px solid #eee}}
/* 산업별 분석 탭 */
.ind-section{{background:#fff;margin:.6rem .75rem;border-radius:14px;border:1px solid #eee;overflow:hidden}}
.ind-section-title{{font-size:.78rem;font-weight:800;color:#fff;background:#1e293b;padding:.55rem 1rem;letter-spacing:.05em}}
.ind-row{{display:grid;grid-template-columns:1fr 1fr 1.1fr 1.1fr;gap:.3rem;padding:.6rem 1rem;border-bottom:1px solid #f3f3f3;align-items:center}}
.ind-row:last-child{{border-bottom:none}}
.ind-sname{{font-size:.84rem;font-weight:700;color:#111;display:block}}
.ind-code{{font-size:.68rem;color:#bbb}}
.ind-price{{font-size:.82rem;font-weight:600;display:block}}
.ind-chg{{font-size:.72rem;font-weight:600;display:block}}
.ind-nxt{{font-size:.65rem;color:#999;display:block}}
.rsi-label-row{{display:flex;justify-content:space-between;margin-bottom:3px}}
.rsi-label{{font-size:.63rem;color:#999}}
.rsi-val{{font-size:.75rem;font-weight:700}}
.rsi-bar-bg{{position:relative;background:#eee;border-radius:99px;height:5px}}
.rsi-bar{{height:5px;border-radius:99px}}
.rsi-mark30{{position:absolute;left:30%;top:-2px;width:1px;height:9px;background:#aaa;opacity:.4}}
.rsi-mark70{{position:absolute;left:70%;top:-2px;width:1px;height:9px;background:#aaa;opacity:.4}}
.ind-levels{{font-size:.7rem}}
.level-row{{display:flex;justify-content:space-between;padding:1px 0}}
.lk{{color:#999;width:30px}}
.lv{{font-weight:600}}
.lv.poc{{color:#7c3aed}}
.lv.sup{{color:#059669}}
.lv.res{{color:#dc2626}}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-title">📈 AI 종목추천</div>
  <div class="topbar-date">{today} {now_str}</div>
</div>

<div class="tab-nav">
  <button class="tab-btn active" onclick="switchTab('recommend')">오늘의 추천</button>
  <button class="tab-btn" onclick="switchTab('industry')">산업별 분석</button>
</div>

<!-- 탭1: 오늘의 추천 -->
<div class="tab-panel active" id="tab-recommend">

{('<div class="section-label">섹터 동향 (ETF 등락률)</div><div class="sector-wrap">' + sector_html + '</div>') if sector_html else ''}

{('<div class="section-label">시장 분석</div><div class="market-box">' + market_txt + '</div>') if market_txt else ''}

<div class="section-label">오늘의 종목 TOP 5</div>
{items}

<div class="section-label">ETF 추천</div>
{etf_items}

{('<div class="section-label">오늘의 전략</div><div class="strategy-box">💡 ' + strategy_txt + '</div>') if strategy_txt else ''}

<div class="update-time" id="last-update">현재가 갱신 중...</div>
<div class="footer">⚠️ 본 리포트는 AI 분석 결과이며 투자 손익의 책임은 본인에게 있습니다.</div>
</div>

<!-- 탭2: 산업별 분석 -->
<div class="tab-panel" id="tab-industry">
<div class="section-label">산업별 시총 상위 · RSI · 매물대 · 지지/저항</div>
{industry_tab_html if industry_tab_html else '<div style="padding:2rem;text-align:center;color:#bbb;font-size:.88rem">산업 데이터 수집 중... 처음 실행 시 시간이 걸릴 수 있습니다.</div>'}
<div class="footer">RSI 기준선: 30(과매도) / 70(과매수) · 매물대(보라) · 지지(초록) · 저항(빨강)</div>
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.tab-btn').forEach((b,i)=>b.classList.toggle('active',['recommend','industry'][i]===name));
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.id==='tab-'+name));
}}
const codes = {codes_json};
async function updatePrices() {{
  for (const [code, ticker] of Object.entries(codes)) {{
    try {{
      const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${{ticker}}?interval=1d&range=1d`);
      const meta = (await r.json())?.chart?.result?.[0]?.meta;
      if (!meta) continue;
      const price = meta.regularMarketPrice;
      const chg = ((price - meta.previousClose) / meta.previousClose * 100);
      const isPos = chg >= 0;
      const pe = document.getElementById('price-' + code);
      const ce = document.getElementById('change-' + code);
      if (pe) pe.textContent = price.toLocaleString('ko-KR') + '원';
      if (ce) {{
        ce.textContent = (isPos ? '▲ ' : '▼ ') + Math.abs(chg).toFixed(2) + '%';
        ce.className = 'schange ' + (isPos ? 'pos' : 'neg');
      }}
    }} catch(e) {{}}
  }}
  document.getElementById('last-update').textContent = '현재가 갱신: ' + new Date().toLocaleTimeString('ko-KR');
}}
updatePrices();
setInterval(updatePrices, 30000);
</script>
</body>
</html>"""

    path = Path(f"report_{date_str}.html")
    path.write_text(html, encoding="utf-8")
    return path


def send_kakao(message: str) -> bool:
    if not KAKAO_TOKEN_FILE.exists(): return False
    token = json.loads(KAKAO_TOKEN_FILE.read_text()).get("access_token", "")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"}
    template = {"object_type": "text", "text": message[:1000], "link": {"web_url": "", "mobile_web_url": ""}}
    resp = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                         headers=headers, data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=10)
    if resp.status_code == 401:
        print("카카오 토큰 만료 → python setup_kakao.py 재실행")
        return False
    return resp.status_code == 200


def run():
    print(f"\n📊 분석 시작 ({datetime.now().strftime('%H:%M')})")
    print("주식 스캔 중", end="")
    stocks = scan(STOCKS)
    print()
    print("ETF 스캔 중", end="")
    etfs = scan(ETFS, is_etf=True)
    print()

    if not stocks:
        print("❌ 분석 종목 없음"); return

    top5 = stocks[:5]
    top_etf = etfs[:2]
    print(f"✅ 주식: {[s['name'] for s in top5]}")
    print(f"✅ ETF:  {[e['name'] for e in top_etf]}")

    print("📊 섹터 ETF 분석 중...")
    sector_perf = get_sector_performance()

    print("🤖 AI 분석 중...")
    ai_text = ask_gemini(top5, top_etf)

    print("🏭 산업별 분석 중 (80종목, 약 1~2분)...")
    industry_data = scan_industry()
    print(f"✅ 산업 {len(industry_data)}개 완료")

    # HTML 리포트 저장 + 브라우저 열기
    html_path = save_html(ai_text, top5, top_etf, sector_perf, industry_data)
    webbrowser.open(f"file://{html_path.resolve()}")
    print(f"✅ 리포트 열림: {html_path}")

    # 카카오톡
    today = datetime.now().strftime("%Y년 %m월 %d일")
    kakao_msg = f"📈 주식 추천 TOP 5 ({today})\n\n" + "\n".join(
        f"{i}위 {s['name']} | {s['price']:,}원 ({s['change']:+.1f}%) | 목표가 {int(s['price']*1.07):,}원"
        for i, s in enumerate(top5, 1)
    ) + f"\n\n자세한 분석은 리포트를 확인하세요.\n⚠️ 투자 책임은 본인에게 있습니다."

    if send_kakao(kakao_msg):
        print("✅ 카카오톡 전송 완료!")


if __name__ == "__main__":
    import sys
    if "--auto" in sys.argv:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz
        KST = pytz.timezone("Asia/Seoul")
        scheduler = BlockingScheduler(timezone=KST)
        scheduler.add_job(run, CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=KST))
        print("⏰ 평일 8:30 자동 실행. 종료: Ctrl+C")
        run()
        try:
            scheduler.start()
        except KeyboardInterrupt:
            print("종료")
    else:
        run()
