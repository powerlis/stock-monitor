import requests
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore


STOCK_CODE = "0048K0"
STOCK_NAME = "KODEX 차이나휴머노이드로봇"
FIREBASE_KEY_FILE = "firebase-service-key.json"
ETF_NAVER_URL = "https://m.stock.naver.com/domestic/stock/0048K0/total"
NAVER_API_URL = f"https://api.stock.naver.com/stock/{STOCK_CODE}/basic"


def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def to_int(value):
    if value is None:
        return 0

    text = str(value).replace(",", "").replace("+", "").strip()

    if text in ["", "-", "N/A"]:
        return 0

    try:
        return int(float(text))
    except Exception:
        return 0


def get_value(data, *keys):
    for key in keys:
        if key in data and data[key] not in [None, "", "-"]:
            return data[key]
    return 0


def get_etf_price_from_naver_api():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": ETF_NAVER_URL,
        "Accept": "application/json"
    }

    response = requests.get(NAVER_API_URL, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()

    print("네이버 API 응답:")
    print(data)

    current = to_int(get_value(data, "closePrice", "nowVal", "localTradedAt"))
    previous = to_int(get_value(data, "compareToPreviousClosePrice", "previousClosePrice"))

    # compareToPreviousClosePrice는 '등락금액'인 경우가 많아서 전일가 보정
    if previous != 0 and current != 0 and abs(previous) < current * 0.3:
        previous = current - previous

    open_price = to_int(get_value(data, "openPrice"))
    high = to_int(get_value(data, "highPrice"))
    low = to_int(get_value(data, "lowPrice"))
    volume = to_int(get_value(data, "accumulatedTradingVolume", "accumulatedTradingValue"))

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
        "source": "NAVER_API",
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    if stock_data["current"] == 0:
        raise Exception("네이버 API에서 현재가를 찾지 못했습니다.")

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

    stock_data = get_etf_price_from_naver_api()
    print("네이버 API ETF 데이터 수집 성공")
    print(stock_data)

    update_firestore(db, stock_data)


if __name__ == "__main__":
    main()