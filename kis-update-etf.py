import json
import re
from datetime import datetime

import requests
import firebase_admin
from firebase_admin import credentials, firestore


STOCK_CODE = "0048K0"
STOCK_NAME = "KODEX 차이나휴머노이드로봇"
FIREBASE_KEY_FILE = "firebase-service-key.json"
ETF_NAVER_URL = "https://m.stock.naver.com/domestic/stock/0048K0/total"


def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def to_int(value):
    if value is None:
        return 0

    text = str(value)
    text = text.replace(",", "")
    text = text.replace("+", "")
    text = text.replace("-", "")
    text = text.strip()

    if text == "" or text.lower() in ["none", "null", "nan"]:
        return 0

    try:
        return int(float(text))
    except Exception:
        return 0


def find_first_value(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in [None, "", "-"]:
                return obj[key]

        for value in obj.values():
            found = find_first_value(value, keys)
            if found not in [None, "", 0]:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_first_value(item, keys)
            if found not in [None, "", 0]:
                return found

    return None


def extract_next_data(html):
    pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except Exception:
        return None


def fallback_find_number(label, html):
    patterns = [
        rf'"{label}".*?"value"\s*:\s*"([\d,]+)"',
        rf'"{label}".*?"value"\s*:\s*([\d,]+)',
        rf'{label}.*?([\d,]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return to_int(match.group(1))

    return 0


def get_etf_price_from_naver_mobile():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": ETF_NAVER_URL,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    response = requests.get(ETF_NAVER_URL, headers=headers, timeout=15)
    response.raise_for_status()

    html = response.text
    next_data = extract_next_data(html)

    current = 0
    previous = 0
    open_price = 0
    high = 0
    low = 0
    volume = 0

    if next_data:
        current = to_int(find_first_value(next_data, [
            "closePrice",
            "nowVal",
            "currentPrice",
            "tradePrice"
        ]))

        previous = to_int(find_first_value(next_data, [
            "previousClosePrice",
            "compareToPreviousClosePrice",
            "prevClosePrice"
        ]))

        open_price = to_int(find_first_value(next_data, [
            "openPrice",
            "open",
            "openingPrice"
        ]))

        high = to_int(find_first_value(next_data, [
            "highPrice",
            "high",
            "highestPrice"
        ]))

        low = to_int(find_first_value(next_data, [
            "lowPrice",
            "low",
            "lowestPrice"
        ]))

        volume = to_int(find_first_value(next_data, [
            "accumulatedTradingVolume",
            "tradingVolume",
            "volume"
        ]))

    if current == 0:
        current_match = re.search(r'"closePrice"\s*:\s*"([\d,]+)"', html)
        if not current_match:
            current_match = re.search(r'"nowVal"\s*:\s*"([\d,]+)"', html)

        if current_match:
            current = to_int(current_match.group(1))

    if previous == 0:
        previous = fallback_find_number("전일", html)

    if open_price == 0:
        open_price = fallback_find_number("시가", html)

    if high == 0:
        high = fallback_find_number("고가", html)

    if low == 0:
        low = fallback_find_number("저가", html)

    if volume == 0:
        volume = fallback_find_number("거래량", html)

    if current == 0:
        raise Exception("네이버 모바일 페이지에서 ETF 현재가를 찾지 못했습니다.")

    if previous != 0 and abs(previous) < current * 0.3:
        previous = current - previous

    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    stock_data = {
        "type": "ETF",
        "name": STOCK_NAME,
        "code": STOCK_CODE,
        "naverUrl": ETF_NAVER_URL,
        "current": current,
        "previous": previous,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
        "market": "한국",
        "source": "NAVER_MOBILE",
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    print("수집 데이터:", stock_data)

    return stock_data


def update_firestore(db, stock_data):
    now = datetime.now()

    daily_id = now.strftime("%Y-%m-%d")
    intraday_id = now.strftime("%Y-%m-%d-%H%M")

    stock_ref = db.collection("stocks").document(STOCK_CODE)

    stock_ref.set(stock_data, merge=True)

    daily_data = {
        "date": daily_id,
        "close": stock_data["current"],
        "current": stock_data["current"],
        "previous": stock_data["previous"],
        "open": stock_data["open"],
        "high": stock_data["high"],
        "low": stock_data["low"],
        "volume": stock_data["volume"],
        "source": stock_data["source"],
        "updatedAt": stock_data["updatedAt"],
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    stock_ref.collection("historyDaily").document(daily_id).set(
        daily_data,
        merge=True
    )

    intraday_data = {
        "date": daily_id,
        "time": now.strftime("%H:%M"),
        "dateTime": stock_data["updatedAt"],
        "price": stock_data["current"],
        "current": stock_data["current"],
        "previous": stock_data["previous"],
        "open": stock_data["open"],
        "high": stock_data["high"],
        "low": stock_data["low"],
        "volume": stock_data["volume"],
        "source": stock_data["source"],
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    stock_ref.collection("historyIntraday").document(intraday_id).set(
        intraday_data,
        merge=True
    )

    print("Firestore 현재가 저장 완료")
    print("historyDaily 저장/갱신:", daily_id)
    print("historyIntraday 저장/갱신:", intraday_id)
    print("저장 데이터:", stock_data)


def main():
    db = init_firestore()
    print("Firestore 연결 성공")

    stock_data = get_etf_price_from_naver_mobile()
    print("네이버 모바일 ETF 데이터 수집 성공")

    update_firestore(db, stock_data)


if __name__ == "__main__":
    main()