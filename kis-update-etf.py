import os
import requests
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv


load_dotenv()

APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")

BASE_URL = "https://openapi.koreainvestment.com:9443"
STOCK_CODE = "0048K0"
FIREBASE_KEY_FILE = "firebase-service-key.json"

ETF_NAVER_URL = "https://m.stock.naver.com/domestic/stock/0048K0/total"


def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"

    headers = {
        "content-type": "application/json"
    }

    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }

    response = requests.post(url, headers=headers, json=body)

    print("토큰 요청 상태코드:", response.status_code)
    print("토큰 응답:", response.text)

    response.raise_for_status()

    data = response.json()
    return data["access_token"]


def get_etf_price(access_token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"

    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010100"
    }

    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": STOCK_CODE
    }

    response = requests.get(url, headers=headers, params=params)

    print("KIS 요청 URL:", response.url)
    print("KIS 상태코드:", response.status_code)
    print("KIS 응답 원문:", response.text)

    if response.status_code != 200:
        raise Exception(f"KIS API HTTP 오류: {response.status_code}")

    data = response.json()

    if data.get("rt_cd") != "0":
        raise Exception(f"KIS API 응답 오류: {data}")

    output = data.get("output", {})

    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "type": "ETF",
        "name": "KODEX 차이나휴머노이드로봇",
        "code": STOCK_CODE,
        "naverUrl": ETF_NAVER_URL,
        "current": int(output.get("stck_prpr", 0) or 0),
        "previous": int(output.get("stck_sdpr", 0) or 0),
        "open": int(output.get("stck_oprc", 0) or 0),
        "high": int(output.get("stck_hgpr", 0) or 0),
        "low": int(output.get("stck_lwpr", 0) or 0),
        "volume": int(output.get("acml_vol", 0) or 0),
        "market": "한국",
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
    if not APP_KEY or not APP_SECRET:
        raise Exception("KIS_APP_KEY 또는 KIS_APP_SECRET 없음")

    db = init_firestore()
    print("Firestore 연결 성공")

    token = get_access_token()
    print("KIS Access Token 발급 성공")

    try:
        stock_data = get_etf_price(token)
        update_firestore(db, stock_data)

    except Exception as e:
        print("ETF 갱신 실패:", e)
        print("KIS에서 0048K0 조회 실패. Firestore 저장을 건너뜁니다.")


if __name__ == "__main__":
    main()
