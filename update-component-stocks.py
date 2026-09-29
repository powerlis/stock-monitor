import json
from pathlib import Path
import time
from datetime import datetime

import yfinance as yf
import firebase_admin
from firebase_admin import credentials, firestore

FIREBASE_KEY_FILE = "firebase-service-key.json"

COMPONENT_STOCKS = json.loads(
    Path(__file__).with_name("constituents.json").read_text(encoding="utf-8")
)["stocks"]

def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)
    return firestore.client()

def normalize_yahoo_code(code):
    code = code.upper().strip()

    if code.endswith(".SH"):
        return code.replace(".SH", ".SS")

    if code.endswith(".HK"):
        number = code.split(".")[0]
        return number.zfill(4) + ".HK"

    return code

def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return round(float(value), 4)
    except Exception:
        return default

def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default

def get_quote(stock):
    code = stock["code"]
    yahoo_code = normalize_yahoo_code(code)
    ticker = yf.Ticker(yahoo_code)

    current = 0
    previous = 0
    open_price = 0
    high = 0
    low = 0
    volume = 0

    try:
        info = ticker.fast_info
        current = safe_float(info.get("last_price"))
        previous = safe_float(info.get("previous_close"))
        open_price = safe_float(info.get("open"))
        high = safe_float(info.get("day_high"))
        low = safe_float(info.get("day_low"))
        volume = safe_int(info.get("last_volume"))
    except Exception:
        pass

    if current == 0:
        hist = ticker.history(period="5d", interval="1d")

        if not hist.empty:
            last = hist.iloc[-1]

            current = safe_float(last["Close"])
            open_price = safe_float(last["Open"])
            high = safe_float(last["High"])
            low = safe_float(last["Low"])
            volume = safe_int(last["Volume"])

            if len(hist) >= 2:
                previous = safe_float(hist.iloc[-2]["Close"])
            else:
                previous = current

    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "rank": stock["rank"],
        "type": "COMPONENT",
        "name": stock["name"],
        "code": code,
        "yahooCode": yahoo_code,
        "naverUrl": stock["naverUrl"],
        "weight": stock["weight"],
        "active": True,
        "current": current,
        "previous": previous,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
        "market": stock["market"],
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

def update_firestore(db, stock_data):
    now = datetime.now()

    code = stock_data["code"]
    daily_id = now.strftime("%Y-%m-%d")
    intraday_id = now.strftime("%Y-%m-%d-%H%M")

    stock_ref = db.collection("stocks").document(code)

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
        "updatedAt": stock_data["updatedAt"],
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

    stock_ref.collection("historyDaily").document(daily_id).set(daily_data, merge=True)

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
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

    stock_ref.collection("historyIntraday").document(intraday_id).set(intraday_data, merge=True)

    print(f"저장 완료: {code} / {stock_data['name']} / 현재가 {stock_data['current']}")

def sync_constituents(db):
    """Refresh membership before quotes; keep old price history intact."""
    active = {stock["code"] for stock in COMPONENT_STOCKS}
    for snapshot in db.collection("stocks").stream():
        if snapshot.to_dict().get("type") == "COMPONENT" and snapshot.id not in active:
            snapshot.reference.set({"active": False}, merge=True)
    for stock in COMPONENT_STOCKS:
        db.collection("stocks").document(stock["code"]).set(
            {**stock, "type": "COMPONENT", "active": True}, merge=True
        )

def main():
    db = init_firestore()
    print("Firestore 연결 성공")

    sync_constituents(db)

    for stock in COMPONENT_STOCKS:
        try:
            quote = get_quote(stock)

            if quote["current"] == 0:
                print(f"조회 실패: {stock['code']} / {stock['name']}")
                continue

            update_firestore(db, quote)

        except Exception as e:
            print(f"오류: {stock['code']} / {stock['name']} / {e}")

        time.sleep(1)

    print("구성종목 업데이트 완료")

if __name__ == "__main__":
    main()