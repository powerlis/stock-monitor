import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
import firebase_admin
from firebase_admin import credentials, firestore


STOCK_CODE = "0048K0"
STOCK_NAME = "KODEX 차이나휴머노이드로봇"
FIREBASE_KEY_FILE = "firebase-service-key.json"

ETF_NAVER_URL = (
    "https://m.stock.naver.com/domestic/stock/0048K0/total"
)

KST = ZoneInfo("Asia/Seoul")


def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def now_kst():
    return datetime.now(KST)


def parse_number(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if text.lower() in {
        "",
        "-",
        "none",
        "null",
        "nan",
        "n/a"
    }:
        return None

    text = (
        text.replace(",", "")
        .replace("원", "")
        .replace("%", "")
        .replace("주", "")
        .strip()
    )

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def to_int(value: Any) -> int:
    number = parse_number(value)

    if number is None:
        return 0

    return int(round(number))


def extract_next_data(html: str) -> dict | None:
    pattern = (
        r'<script[^>]+id=["\']__NEXT_DATA__["\']'
        r'[^>]*>(.*?)</script>'
    )

    match = re.search(pattern, html, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def direct_value(data: dict, keys: list[str]):
    """
    현재 객체의 직접 필드만 검사합니다.
    하위 객체를 재귀 탐색하지 않습니다.
    """
    for key in keys:
        if key not in data:
            continue

        value = data.get(key)

        if value not in [None, "", "-"]:
            return value

    return None


def direct_int(data: dict, keys: list[str]) -> int:
    return to_int(direct_value(data, keys))


def contains_stock_code(data: dict) -> bool:
    code_keys = [
        "stockCode",
        "itemCode",
        "code",
        "symbolCode",
        "reutersCode"
    ]

    for key in code_keys:
        value = str(data.get(key, "")).upper()

        if STOCK_CODE in value:
            return True

    return False


def get_direction_text(data: dict) -> str:
    values = []

    for key in [
        "compareToPreviousPrice",
        "compareToPreviousClosePriceType",
        "changeType",
        "fluctuationsRatioType"
    ]:
        value = data.get(key)

        if isinstance(value, dict):
            values.extend(str(item) for item in value.values())

        elif value is not None:
            values.append(str(value))

    return " ".join(values).lower()


def signed_change_amount(data: dict) -> int:
    raw_value = direct_value(
        data,
        [
            "compareToPreviousClosePrice",
            "changePrice",
            "priceChange"
        ]
    )

    number = parse_number(raw_value)

    if number is None:
        return 0

    raw_text = str(raw_value).strip()

    # 값 자체에 음수 기호가 있으면 그대로 하락 처리
    if raw_text.startswith("-") or number < 0:
        return -abs(int(round(number)))

    direction = get_direction_text(data)

    # 네이버 등락 구분 코드:
    # 2 상승, 3 보합, 5 하락
    if (
        "하락" in direction
        or "내림" in direction
        or "down" in direction
        or "fall" in direction
        or direction.strip() == "5"
        or '"code": "5"' in direction
    ):
        return -abs(int(round(number)))

    if (
        "보합" in direction
        or "unchanged" in direction
        or "flat" in direction
        or direction.strip() == "3"
        or '"code": "3"' in direction
    ):
        return 0

    return abs(int(round(number)))


def build_candidate(data: dict) -> dict | None:
    """
    한 객체 안에 시세 관련 필드가 직접 같이 있는 경우만 후보로 인정합니다.
    """
    current = direct_int(
        data,
        [
            "closePrice",
            "currentPrice",
            "nowVal",
            "tradePrice"
        ]
    )

    open_price = direct_int(
        data,
        [
            "openPrice",
            "openingPrice"
        ]
    )

    high = direct_int(
        data,
        [
            "highPrice",
            "highestPrice"
        ]
    )

    low = direct_int(
        data,
        [
            "lowPrice",
            "lowestPrice"
        ]
    )

    volume = direct_int(
        data,
        [
            "accumulatedTradingVolume",
            "tradingVolume",
            "volume"
        ]
    )

    change_amount = signed_change_amount(data)

    # 필수 가격이 모두 같은 객체에 있어야 함
    if not all([
        current > 0,
        open_price > 0,
        high > 0,
        low > 0
    ]):
        return None

    # 가격 관계 검증
    if high < low:
        return None

    if not (low <= current <= high):
        return None

    if not (low <= open_price <= high):
        return None

    # 전일 대비 금액이 없으면 후보로 사용하지 않음
    if change_amount == 0:
        direction = get_direction_text(data)

        if not (
            "보합" in direction
            or "unchanged" in direction
            or direction.strip() == "3"
        ):
            return None

    previous = current - change_amount

    if previous <= 0:
        return None

    # 비정상적인 전일가 차단
    if abs(current - previous) / previous > 0.30:
        return None

    score = 0

    if contains_stock_code(data):
        score += 100

    if "closePrice" in data:
        score += 20

    if "compareToPreviousClosePrice" in data:
        score += 20

    if "openPrice" in data:
        score += 10

    if "highPrice" in data:
        score += 10

    if "lowPrice" in data:
        score += 10

    if "accumulatedTradingVolume" in data:
        score += 10

    return {
        "score": score,
        "raw": data,
        "current": current,
        "previous": previous,
        "change": change_amount,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume
    }


def find_quote_candidate(next_data: dict) -> dict:
    candidates = []

    for data in walk_dicts(next_data):
        candidate = build_candidate(data)

        if candidate:
            candidates.append(candidate)

    if not candidates:
        raise RuntimeError(
            "현재가·시가·고가·저가·전일 대비 금액이 "
            "같이 들어 있는 시세 객체를 찾지 못했습니다."
        )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    best = candidates[0]

    print("선택된 후보 점수:", best["score"])
    print(
        "선택된 원본 객체:",
        json.dumps(
            best["raw"],
            ensure_ascii=False,
            indent=2
        )[:5000]
    )

    return best


def get_etf_price_from_naver_mobile() -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": ETF_NAVER_URL,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

    response = requests.get(
        ETF_NAVER_URL,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    next_data = extract_next_data(response.text)

    if next_data is None:
        raise RuntimeError(
            "네이버 모바일 페이지에서 __NEXT_DATA__를 찾지 못했습니다."
        )

    quote = find_quote_candidate(next_data)

    current = quote["current"]
    previous = quote["previous"]
    change = quote["change"]

    # 핵심 교차검증
    if current - previous != change:
        raise RuntimeError(
            "현재가, 전일가, 전일 대비 금액의 계산이 일치하지 않습니다."
        )

    now = now_kst()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    change_rate = (
        ((current - previous) / previous) * 100
        if previous > 0
        else 0
    )

    stock_data = {
        "type": "ETF",
        "name": STOCK_NAME,
        "code": STOCK_CODE,
        "naverUrl": ETF_NAVER_URL,
        "current": current,
        "previous": previous,
        "change": change,
        "changeRate": round(change_rate, 4),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "volume": quote["volume"],
        "market": "한국",
        "source": "NAVER_MOBILE_EXACT_OBJECT",
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    print(
        "최종 수집 데이터:",
        json.dumps(
            {
                key: value
                for key, value in stock_data.items()
                if key != "timestamp"
            },
            ensure_ascii=False,
            indent=2
        )
    )

    return stock_data


def update_firestore(db, stock_data: dict):
    now = now_kst()

    daily_id = now.strftime("%Y-%m-%d")
    intraday_id = now.strftime("%Y-%m-%d-%H%M")

    stock_ref = (
        db.collection("stocks")
        .document(STOCK_CODE)
    )

    stock_ref.set(
        stock_data,
        merge=True
    )

    daily_data = {
        "date": daily_id,
        "close": stock_data["current"],
        "current": stock_data["current"],
        "previous": stock_data["previous"],
        "change": stock_data["change"],
        "changeRate": stock_data["changeRate"],
        "open": stock_data["open"],
        "high": stock_data["high"],
        "low": stock_data["low"],
        "volume": stock_data["volume"],
        "source": stock_data["source"],
        "updatedAt": stock_data["updatedAt"],
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    (
        stock_ref
        .collection("historyDaily")
        .document(daily_id)
        .set(daily_data, merge=True)
    )

    intraday_data = {
        "date": daily_id,
        "time": now.strftime("%H:%M"),
        "dateTime": stock_data["updatedAt"],
        "price": stock_data["current"],
        "current": stock_data["current"],
        "previous": stock_data["previous"],
        "change": stock_data["change"],
        "changeRate": stock_data["changeRate"],
        "open": stock_data["open"],
        "high": stock_data["high"],
        "low": stock_data["low"],
        "volume": stock_data["volume"],
        "source": stock_data["source"],
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    (
        stock_ref
        .collection("historyIntraday")
        .document(intraday_id)
        .set(intraday_data, merge=True)
    )

    print("Firestore 저장 완료")
    print("현재가:", stock_data["current"])
    print("전일가:", stock_data["previous"])
    print("등락:", stock_data["change"])
    print("시가:", stock_data["open"])
    print("고가:", stock_data["high"])
    print("저가:", stock_data["low"])


def main():
    print("ETF 데이터 업데이트 시작")

    db = init_firestore()
    print("Firestore 연결 성공")

    stock_data = get_etf_price_from_naver_mobile()

    # 저장 전에 터미널에서 반드시 확인
    print(
        "검증 결과:",
        f"현재가 {stock_data['current']} / "
        f"전일가 {stock_data['previous']} / "
        f"등락 {stock_data['change']}"
    )

    update_firestore(db, stock_data)

    print("ETF 데이터 업데이트 완료")


if __name__ == "__main__":
    main()