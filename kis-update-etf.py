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


def clean_number(value: Any) -> float | None:
    """
    쉼표, %, 원 등의 문자를 제거하고 숫자로 변환합니다.
    부호는 유지합니다.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if text == "" or text.lower() in {
        "none",
        "null",
        "nan",
        "n/a",
        "-"
    }:
        return None

    text = text.replace(",", "")
    text = text.replace("원", "")
    text = text.replace("%", "")
    text = text.replace("주", "")
    text = text.strip()

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def to_int(value: Any) -> int:
    number = clean_number(value)

    if number is None:
        return 0

    return int(round(number))


def extract_next_data(html: str) -> dict | None:
    """
    네이버 모바일 페이지에 포함된 __NEXT_DATA__ JSON을 추출합니다.
    """
    patterns = [
        (
            r'<script[^>]+id=["\']__NEXT_DATA__["\']'
            r'[^>]*>(.*?)</script>'
        ),
        (
            r'<script[^>]+type=["\']application/json["\']'
            r'[^>]+id=["\']__NEXT_DATA__["\']'
            r'[^>]*>(.*?)</script>'
        )
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            continue

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

    return None


def walk_dicts(value: Any):
    """
    중첩 JSON 안의 모든 dict 객체를 순회합니다.
    """
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def contains_stock_code(data: dict) -> bool:
    """
    해당 객체가 0048K0 종목과 관련된 객체인지 확인합니다.
    """
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

    serialized = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return STOCK_CODE in serialized


def score_quote_object(data: dict) -> int:
    """
    시세 객체일 가능성을 점수로 평가합니다.
    여러 화면 데이터 중 엉뚱한 값을 선택하지 않도록 합니다.
    """
    score = 0

    primary_keys = [
        "closePrice",
        "currentPrice",
        "nowVal",
        "tradePrice"
    ]

    market_keys = [
        "openPrice",
        "highPrice",
        "lowPrice"
    ]

    previous_keys = [
        "previousClosePrice",
        "prevClosePrice",
        "compareToPreviousClosePrice"
    ]

    volume_keys = [
        "accumulatedTradingVolume",
        "tradingVolume",
        "volume"
    ]

    if any(key in data for key in primary_keys):
        score += 10

    score += sum(
        3 for key in market_keys
        if key in data
    )

    score += sum(
        3 for key in previous_keys
        if key in data
    )

    score += sum(
        2 for key in volume_keys
        if key in data
    )

    if contains_stock_code(data):
        score += 15

    name_text = " ".join(
        str(data.get(key, ""))
        for key in [
            "stockName",
            "itemName",
            "name",
            "localName"
        ]
    )

    if (
        "차이나휴머노이드" in name_text
        or "KODEX" in name_text
    ):
        score += 10

    return score


def find_quote_object(next_data: dict) -> dict:
    """
    현재가, 시가, 고가, 저가 등이 함께 들어 있는
    가장 신뢰할 수 있는 단일 객체를 선택합니다.
    """
    candidates = []

    for data in walk_dicts(next_data):
        score = score_quote_object(data)

        if score > 0:
            candidates.append((score, data))

    if not candidates:
        raise RuntimeError(
            "네이버 페이지에서 시세 객체를 찾지 못했습니다."
        )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    best_score, best_data = candidates[0]

    print("선택된 시세 객체 점수:", best_score)
    print(
        "선택된 시세 객체:",
        json.dumps(
            best_data,
            ensure_ascii=False,
            indent=2
        )[:5000]
    )

    if best_score < 20:
        raise RuntimeError(
            "시세 객체의 신뢰 점수가 낮아 저장을 중단합니다."
        )

    return best_data


def first_number(data: dict, keys: list[str]) -> int:
    for key in keys:
        if key not in data:
            continue

        value = to_int(data.get(key))

        if value != 0:
            return value

    return 0


def determine_change_amount(data: dict) -> int:
    """
    전일 대비 금액의 부호를 정확히 판단합니다.
    """
    raw_change = None

    for key in [
        "compareToPreviousClosePrice",
        "changePrice",
        "priceChange"
    ]:
        if key in data:
            raw_change = data.get(key)
            break

    number = clean_number(raw_change)

    if number is None:
        return 0

    raw_text = str(raw_change).strip()

    # 값 자체에 음수 부호가 있으면 그대로 사용
    if raw_text.startswith("-"):
        return -abs(int(round(number)))

    direction_values = []

    for key in [
        "compareToPreviousPrice",
        "compareToPreviousClosePriceType",
        "fluctuationsRatioType",
        "changeType"
    ]:
        value = data.get(key)

        if isinstance(value, dict):
            direction_values.extend(
                str(item)
                for item in value.values()
            )
        elif value is not None:
            direction_values.append(str(value))

    direction_text = " ".join(direction_values).lower()

    down_words = [
        "하락",
        "내림",
        "fall",
        "down",
        "lower",
        "5"
    ]

    flat_words = [
        "보합",
        "unchanged",
        "flat",
        "3"
    ]

    if any(word in direction_text for word in flat_words):
        return 0

    if any(word in direction_text for word in down_words):
        return -abs(int(round(number)))

    return abs(int(round(number)))


def build_stock_data(quote: dict) -> dict:
    current = first_number(
        quote,
        [
            "closePrice",
            "currentPrice",
            "nowVal",
            "tradePrice"
        ]
    )

    open_price = first_number(
        quote,
        [
            "openPrice",
            "openingPrice",
            "open"
        ]
    )

    high = first_number(
        quote,
        [
            "highPrice",
            "highestPrice",
            "high"
        ]
    )

    low = first_number(
        quote,
        [
            "lowPrice",
            "lowestPrice",
            "low"
        ]
    )

    volume = first_number(
        quote,
        [
            "accumulatedTradingVolume",
            "tradingVolume",
            "volume"
        ]
    )

    # 전일 종가 필드만 우선 사용합니다.
    previous = first_number(
        quote,
        [
            "previousClosePrice",
            "prevClosePrice"
        ]
    )

    change_amount = determine_change_amount(quote)

    # 전일 종가 필드가 없을 때만 현재가와 등락금액으로 계산
    if previous == 0 and current > 0:
        previous = current - change_amount

    validate_quote(
        current=current,
        previous=previous,
        open_price=open_price,
        high=high,
        low=low,
        volume=volume
    )

    now = now_kst()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    change_rate = (
        ((current - previous) / previous) * 100
        if previous > 0
        else 0
    )

    return {
        "type": "ETF",
        "name": STOCK_NAME,
        "code": STOCK_CODE,
        "naverUrl": ETF_NAVER_URL,
        "current": current,
        "previous": previous,
        "change": current - previous,
        "changeRate": round(change_rate, 4),
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
        "market": "한국",
        "source": "NAVER_MOBILE_NEXT_DATA",
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP
    }


def validate_quote(
    current: int,
    previous: int,
    open_price: int,
    high: int,
    low: int,
    volume: int
):
    """
    엉뚱한 숫자가 Firestore에 덮어써지는 것을 방지합니다.
    """
    errors = []

    if current <= 0:
        errors.append("현재가가 0 이하입니다.")

    if previous <= 0:
        errors.append("전일가가 0 이하입니다.")

    if open_price <= 0:
        errors.append("시가가 0 이하입니다.")

    if high <= 0:
        errors.append("고가가 0 이하입니다.")

    if low <= 0:
        errors.append("저가가 0 이하입니다.")

    if high < low:
        errors.append("고가가 저가보다 낮습니다.")

    if high > 0 and current > high:
        errors.append("현재가가 고가보다 높습니다.")

    if low > 0 and current < low:
        errors.append("현재가가 저가보다 낮습니다.")

    if high > 0 and open_price > high:
        errors.append("시가가 고가보다 높습니다.")

    if low > 0 and open_price < low:
        errors.append("시가가 저가보다 낮습니다.")

    if current > 0 and previous > 0:
        variation = abs(current - previous) / previous

        if variation > 0.30:
            errors.append(
                "현재가와 전일가의 차이가 30%를 초과합니다."
            )

    if volume < 0:
        errors.append("거래량이 음수입니다.")

    if errors:
        message = "\n".join(
            f"- {error}"
            for error in errors
        )

        raise RuntimeError(
            "수집 데이터 검증 실패. Firestore에 저장하지 않습니다.\n"
            + message
        )


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
            "application/xml;q=0.9,image/avif,"
            "image/webp,*/*;q=0.8"
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

    html = response.text

    next_data = extract_next_data(html)

    if next_data is None:
        raise RuntimeError(
            "네이버 모바일 페이지에서 __NEXT_DATA__를 "
            "찾지 못했습니다."
        )

    quote = find_quote_object(next_data)
    stock_data = build_stock_data(quote)

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
    print("현재 문서:", f"stocks/{STOCK_CODE}")
    print(
        "일별 문서:",
        f"stocks/{STOCK_CODE}/historyDaily/{daily_id}"
    )
    print(
        "당일 문서:",
        (
            f"stocks/{STOCK_CODE}/"
            f"historyIntraday/{intraday_id}"
        )
    )


def main():
    print("ETF 데이터 업데이트 시작")

    db = init_firestore()
    print("Firestore 연결 성공")

    stock_data = get_etf_price_from_naver_mobile()
    print("네이버 모바일 ETF 데이터 수집 성공")

    update_firestore(db, stock_data)

    print("ETF 데이터 업데이트 완료")


if __name__ == "__main__":
    main()