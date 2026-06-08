import re
import requests
from datetime import datetime

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
    return int(str(value).replace(",", "").strip() or 0)


def find_number_after(label, html):
    pattern = rf'"{label}".*?"value":"([\d,]+)"'
    match = re.search(pattern, html)
    if match:
        return to_int(match.group(1))
    return 0


def get_etf_price_from_naver():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": ETF_NAVER_URL
    }

    response = requests.get(ETF_NAVER_URL, headers=headers, timeout=10)
    response.raise_for_status()

    html = response.text

    current_match = re.search(r'"closePrice":"([\d,]+)"', html)
    if not current_match:
        current_match = re.search(r'"nowVal":"([\d,]+)"', html)

    if not current_match:
        raise Exception("네이버에서 현재가를 찾지 못했습니다.")

    current = to_int(current_match.group(1))

    previous = find_number_after("전일", html)
    open_price = find_number_after("시가", html)
    high = find_number_after("고가", html)
    low = find_number_after("저가", html)
    volume = find_number_after("거래량", html)

    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    return {
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
        "source": "NAVER",
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP
    }


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

    stock_data = get_etf_price_from_naver()
    print("네이버 ETF 데이터 수집 성공")
    print(stock_data)

    update_firestore(db, stock_data)


if __name__ == "__main__":
    main()
