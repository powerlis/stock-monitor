import html as html_module
import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import firebase_admin
import requests
from firebase_admin import credentials, firestore


STOCK_CODE = "0048K0"
STOCK_NAME = "KODEX 차이나휴머노이드로봇"

FIREBASE_KEY_FILE = "firebase-service-key.json"

ETF_NAVER_URL = (
    "https://m.stock.naver.com/domestic/stock/0048K0/total"
)

KST = ZoneInfo("Asia/Seoul")


# --------------------------------------------------
# Firebase
# --------------------------------------------------

def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def now_kst():
    return datetime.now(KST)


# --------------------------------------------------
# 숫자 변환
# --------------------------------------------------

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

    text = html_module.unescape(text)

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


# --------------------------------------------------
# HTML·JSON 추출
# --------------------------------------------------

def extract_next_data_text(page_html: str) -> str | None:
    """
    HTML에 포함된 __NEXT_DATA__ JSON 원문을 추출합니다.
    """
    pattern = (
        r'<script[^>]+id=["\']__NEXT_DATA__["\']'
        r'[^>]*>(.*?)</script>'
    )

    match = re.search(
        pattern,
        page_html,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not match:
        return None

    return html_module.unescape(match.group(1))


def extract_next_data(page_html: str) -> dict | None:
    json_text = extract_next_data_text(page_html)

    if not json_text:
        return None

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def walk_dicts(value: Any):
    """
    중첩 JSON의 모든 dict 객체를 순회합니다.
    """
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


# --------------------------------------------------
# 정확한 필드 검색
# --------------------------------------------------

def exact_key_values(data: Any, key_name: str) -> list[Any]:
    """
    JSON 전체에서 정확히 일치하는 키의 값을 모두 찾습니다.

    예:
    previousClosePrice만 찾음
    compareToPreviousClosePrice는 찾지 않음
    """
    results = []

    for item in walk_dicts(data):
        if key_name in item:
            value = item.get(key_name)

            if value not in [None, "", "-"]:
                results.append(value)

    return results


def exact_html_values(page_html: str, key_name: str) -> list[str]:
    """
    JSON 파싱이 불가능한 경우를 대비하여 HTML 원문에서
    정확한 키 이름으로 값들을 찾습니다.
    """
    escaped_key = re.escape(key_name)

    patterns = [
        rf'"{escaped_key}"\s*:\s*"([^"]+)"',
        rf"'{escaped_key}'\s*:\s*'([^']+)'",
        rf'"{escaped_key}"\s*:\s*(-?\d+(?:\.\d+)?)',
        rf"'{escaped_key}'\s*:\s*(-?\d+(?:\.\d+)?)"
    ]

    results = []

    for pattern in patterns:
        matches = re.findall(
            pattern,
            page_html,
            flags=re.DOTALL
        )

        for value in matches:
            if value not in results:
                results.append(value)

    return results


def get_exact_values(
    next_data: dict | None,
    page_html: str,
    key_names: list[str]
) -> list[int]:
    """
    지정한 정확한 키 이름에서 양수 숫자 후보를 수집합니다.
    """
    results = []

    for key_name in key_names:
        raw_values = []

        if next_data is not None:
            raw_values.extend(
                exact_key_values(next_data, key_name)
            )

        raw_values.extend(
            exact_html_values(page_html, key_name)
        )

        for raw_value in raw_values:
            number = to_int(raw_value)

            if number > 0 and number not in results:
                results.append(number)

    return results


def choose_current_price(candidates: list[int]) -> int:
    if not candidates:
        return 0

    # 첫 번째 정확한 closePrice를 우선 사용
    return candidates[0]


def choose_nearby_price(
    candidates: list[int],
    current: int,
    field_name: str,
    maximum_gap_ratio: float = 0.30
) -> int:
    """
    현재가와 지나치게 차이나는 다른 종목·다른 데이터의 값을 제외합니다.
    """
    if not candidates:
        return 0

    valid = []

    for value in candidates:
        if current <= 0:
            valid.append(value)
            continue

        gap_ratio = abs(value - current) / current

        if gap_ratio <= maximum_gap_ratio:
            valid.append(value)

    if not valid:
        print(
            f"{field_name} 후보가 현재가와 지나치게 차이 납니다:",
            candidates
        )
        return 0

    # 현재가와 가장 가까운 값을 선택
    return min(
        valid,
        key=lambda value: abs(value - current)
    )


def choose_volume(candidates: list[int]) -> int:
    if not candidates:
        return 0

    # 거래량은 일반적으로 가장 큰 양수 후보를 사용
    return max(candidates)


# --------------------------------------------------
# 수집값 검증
# --------------------------------------------------

def validate_stock_data(stock_data: dict):
    current = stock_data["current"]
    previous = stock_data["previous"]
    open_price = stock_data["open"]
    high = stock_data["high"]
    low = stock_data["low"]
    volume = stock_data["volume"]

    errors = []

    if current <= 0:
        errors.append("현재가를 찾지 못했습니다.")

    if previous <= 0:
        errors.append(
            "HTML의 previousClosePrice 전일가를 찾지 못했습니다."
        )

    if open_price <= 0:
        errors.append("시가를 찾지 못했습니다.")

    if high <= 0:
        errors.append("고가를 찾지 못했습니다.")

    if low <= 0:
        errors.append("저가를 찾지 못했습니다.")

    if high > 0 and low > 0 and high < low:
        errors.append("고가가 저가보다 낮습니다.")

    if (
        current > 0
        and high > 0
        and low > 0
        and not low <= current <= high
    ):
        errors.append(
            "현재가가 저가와 고가 범위에 들어 있지 않습니다."
        )

    if (
        open_price > 0
        and high > 0
        and low > 0
        and not low <= open_price <= high
    ):
        errors.append(
            "시가가 저가와 고가 범위에 들어 있지 않습니다."
        )

    if current > 0 and previous > 0:
        difference_ratio = abs(current - previous) / previous

        if difference_ratio > 0.30:
            errors.append(
                "현재가와 전일가 차이가 30%를 초과합니다."
            )

    if volume < 0:
        errors.append("거래량이 음수입니다.")

    if errors:
        message = "\n".join(
            f"- {error}"
            for error in errors
        )

        raise RuntimeError(
            "수집 데이터 검증에 실패하여 Firestore 저장을 중단합니다.\n"
            + message
        )


# --------------------------------------------------
# 네이버 모바일 페이지 수집
# --------------------------------------------------

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

    page_html = response.text
    next_data = extract_next_data(page_html)

    if next_data is None:
        print(
            "주의: __NEXT_DATA__ JSON 파싱 실패. "
            "HTML 원문에서 정확한 키를 검색합니다."
        )

    # 현재가: 정확한 closePrice 계열만 사용
    current_candidates = get_exact_values(
        next_data,
        page_html,
        [
            "closePrice",
            "currentPrice",
            "nowVal"
        ]
    )

    current = choose_current_price(
        current_candidates
    )

    # 전일가: 전일가 전용 필드만 사용
    # compareToPreviousClosePrice는 등락금액일 수 있으므로 제외
    previous_candidates = get_exact_values(
        next_data,
        page_html,
        [
            "previousClosePrice",
            "prevClosePrice"
        ]
    )

    previous = choose_nearby_price(
        previous_candidates,
        current,
        "전일가"
    )

    open_candidates = get_exact_values(
        next_data,
        page_html,
        [
            "openPrice",
            "openingPrice"
        ]
    )

    open_price = choose_nearby_price(
        open_candidates,
        current,
        "시가"
    )

    high_candidates = get_exact_values(
        next_data,
        page_html,
        [
            "highPrice",
            "highestPrice"
        ]
    )

    high = choose_nearby_price(
        high_candidates,
        current,
        "고가"
    )

    low_candidates = get_exact_values(
        next_data,
        page_html,
        [
            "lowPrice",
            "lowestPrice"
        ]
    )

    low = choose_nearby_price(
        low_candidates,
        current,
        "저가"
    )

    volume_candidates = get_exact_values(
        next_data,
        page_html,
        [
            "accumulatedTradingVolume",
            "tradingVolume",
            "volume"
        ]
    )

    volume = choose_volume(
        volume_candidates
    )

    print("현재가 후보:", current_candidates)
    print("전일가 후보:", previous_candidates)
    print("시가 후보:", open_candidates)
    print("고가 후보:", high_candidates)
    print("저가 후보:", low_candidates)
    print("거래량 후보:", volume_candidates)

    now = now_kst()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    change = (
        current - previous
        if current > 0 and previous > 0
        else 0
    )

    change_rate = (
        (change / previous) * 100
        if previous > 0
        else 0
    )

    stock_data = {
        "type": "ETF",
        "name": STOCK_NAME,
        "code": STOCK_CODE,
        "naverUrl": ETF_NAVER_URL,

        "current": current,

        # HTML의 previousClosePrice를 그대로 저장
        "previous": previous,

        "change": change,
        "changeRate": round(change_rate, 4),
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,

        "market": "한국",
        "source": "NAVER_MOBILE_EXACT_FIELDS",
        "updatedAt": now_text,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    validate_stock_data(stock_data)

    printable_data = {
        key: value
        for key, value in stock_data.items()
        if key != "timestamp"
    }

    print(
        "최종 수집 데이터:",
        json.dumps(
            printable_data,
            ensure_ascii=False,
            indent=2
        )
    )

    return stock_data


# --------------------------------------------------
# Firestore 저장
# --------------------------------------------------

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
    print("등락률:", stock_data["changeRate"])
    print("시가:", stock_data["open"])
    print("고가:", stock_data["high"])
    print("저가:", stock_data["low"])
    print("거래량:", stock_data["volume"])


# --------------------------------------------------
# 실행
# --------------------------------------------------

def main():
    print("ETF 데이터 업데이트 시작")

    db = init_firestore()
    print("Firestore 연결 성공")

    stock_data = get_etf_price_from_naver_mobile()
    print("네이버 모바일 ETF 데이터 수집 성공")

    print(
        "저장 전 검증:",
        f"현재가 {stock_data['current']}원 / "
        f"전일가 {stock_data['previous']}원 / "
        f"등락 {stock_data['change']}원"
    )

    update_firestore(db, stock_data)

    print("ETF 데이터 업데이트 완료")


if __name__ == "__main__":
    main()