from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import firebase_admin
import requests
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


STOCK_CODE = "0048K0"
STOCK_NAME = "KODEX 차이나휴머노이드로봇"

FIREBASE_KEY_FILE = "firebase-service-key.json"

ETF_NAVER_URL = (
    "https://m.stock.naver.com/domestic/stock/0048K0/total"
)

REALTIME_API_URL = (
    "https://polling.finance.naver.com/"
    "api/realtime/domestic/stock/0048K0"
)

INTEGRATION_API_URL = (
    "https://m.stock.naver.com/api/stock/0048K0/integration"
)

KST = ZoneInfo("Asia/Seoul")


# --------------------------------------------------
# Firebase
# --------------------------------------------------

def init_firestore():
    """Firebase Admin SDK를 초기화하고 Firestore 객체를 반환합니다."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def now_kst() -> datetime:
    """한국 시간을 반환합니다."""
    return datetime.now(KST)


# --------------------------------------------------
# HTTP
# --------------------------------------------------

def create_http_session() -> requests.Session:
    """
    네이버 요청용 Session을 생성합니다.
    일시적인 429 및 5xx 오류는 자동으로 재시도합니다.
    """
    session = requests.Session()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
        "Referer": ETF_NAVER_URL,
        "Origin": "https://m.stock.naver.com",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })

    return session


def request_json(
    session: requests.Session,
    url: str,
) -> dict[str, Any]:
    """URL을 호출하고 JSON 객체를 반환합니다."""
    response = session.get(url, timeout=20)
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as error:
        preview = response.text[:500]

        raise RuntimeError(
            f"JSON 응답이 아닙니다.\nURL: {url}\n응답 일부: {preview}"
        ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            f"예상하지 못한 JSON 형식입니다.\nURL: {url}"
        )

    return data


# --------------------------------------------------
# 숫자 변환
# --------------------------------------------------

def parse_number(value: Any) -> float | None:
    """
    '10,065', '-445', '4.23%', '49.4억' 등의 값에서
    첫 번째 숫자와 부호를 읽습니다.
    """
    if value is None:
        return None

    if isinstance(value, bool):
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
        "n/a",
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


def to_int(value: Any, field_name: str) -> int:
    """필수 정수 필드를 변환합니다."""
    number = parse_number(value)

    if number is None:
        raise RuntimeError(
            f"{field_name} 값을 숫자로 변환하지 못했습니다: {value!r}"
        )

    return int(round(number))


def to_float(value: Any, field_name: str) -> float:
    """필수 실수 필드를 변환합니다."""
    number = parse_number(value)

    if number is None:
        raise RuntimeError(
            f"{field_name} 값을 숫자로 변환하지 못했습니다: {value!r}"
        )

    return float(number)


# --------------------------------------------------
# 실시간 시세 조회
# --------------------------------------------------

def get_realtime_quote(
    session: requests.Session,
) -> dict[str, Any]:
    """
    네이버 실시간 시세 JSON에서 0048K0 데이터를 가져옵니다.
    """
    payload = request_json(session, REALTIME_API_URL)

    # 응답에 isSuccess가 있을 때 false이면 실패 처리
    if payload.get("isSuccess") is False:
        raise RuntimeError(
            "네이버 실시간 시세 응답 실패:\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    result = payload.get("result")

    if isinstance(result, dict):
        datas = result.get("datas")
    else:
        # 일부 응답은 datas가 최상위에 있을 수 있음
        datas = payload.get("datas")

    if not isinstance(datas, list) or not datas:
        raise RuntimeError(
            "네이버 실시간 시세 응답에 datas가 없습니다.\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)[:3000]
        )

    matched_item = None

    for item in datas:
        if not isinstance(item, dict):
            continue

        item_code = str(
            item.get("itemCode")
            or item.get("symbolCode")
            or ""
        ).upper()

        if item_code == STOCK_CODE:
            matched_item = item
            break

    if matched_item is None:
        raise RuntimeError(
            f"실시간 응답에서 {STOCK_CODE} 종목을 찾지 못했습니다."
        )

    print(
        "네이버 실시간 원본 데이터:",
        json.dumps(
            matched_item,
            ensure_ascii=False,
            indent=2,
        )[:6000],
    )

    return matched_item


# --------------------------------------------------
# 전일 종가 조회
# --------------------------------------------------

def find_last_close_price(
    integration_payload: dict[str, Any],
) -> int:
    """
    integration 응답의 totalInfos에서 전일 종가를 찾습니다.

    예상 형식:
    {
        "totalInfos": [
            {
                "code": "lastClosePrice",
                "key": "전일",
                "value": "10,510"
            }
        ]
    }
    """
    total_infos = integration_payload.get("totalInfos")

    if not isinstance(total_infos, list):
        result = integration_payload.get("result")

        if isinstance(result, dict):
            total_infos = result.get("totalInfos")

    if not isinstance(total_infos, list):
        raise RuntimeError(
            "integration 응답에서 totalInfos를 찾지 못했습니다."
        )

    accepted_codes = {
        "lastcloseprice",
        "previouscloseprice",
        "prevcloseprice",
    }

    for info in total_infos:
        if not isinstance(info, dict):
            continue

        code = str(info.get("code", "")).strip().lower()
        key = str(info.get("key", "")).strip()

        if code in accepted_codes or key in {"전일", "전일가", "전일 종가"}:
            value = info.get("value")

            previous = to_int(value, "전일 종가")

            if previous > 0:
                print(
                    "전일 종가 원본 정보:",
                    json.dumps(
                        info,
                        ensure_ascii=False,
                        indent=2,
                    ),
                )

                return previous

    raise RuntimeError(
        "integration 응답에서 전일 종가 항목을 찾지 못했습니다."
    )


def get_previous_close(
    session: requests.Session,
    current: int,
    change: int,
) -> tuple[int, str]:
    """
    전일 종가는 integration API 값을 우선 사용합니다.

    integration API 조회가 실패할 때만
    실시간 응답의 현재가와 공식 등락금액으로 계산합니다.
    """
    try:
        payload = request_json(session, INTEGRATION_API_URL)
        previous = find_last_close_price(payload)

        return previous, "NAVER_INTEGRATION_LAST_CLOSE"

    except Exception as error:
        print("전일 종가 API 조회 실패:", error)
        print(
            "실시간 현재가와 네이버 공식 등락금액으로 "
            "전일 종가를 계산합니다."
        )

        previous = current - change

        if previous <= 0:
            raise RuntimeError(
                "전일 종가 API 조회와 보조 계산이 모두 실패했습니다."
            ) from error

        return previous, "NAVER_REALTIME_CALCULATED_PREVIOUS"


# --------------------------------------------------
# 데이터 구성 및 검증
# --------------------------------------------------

def build_stock_data(
    session: requests.Session,
) -> dict[str, Any]:
    quote = get_realtime_quote(session)

    # Raw 필드를 우선 사용하고, 없으면 표시용 필드를 사용
    current = to_int(
        quote.get("closePriceRaw")
        or quote.get("closePrice"),
        "현재가",
    )

    change = to_int(
        quote.get("compareToPreviousClosePriceRaw")
        or quote.get("compareToPreviousClosePrice"),
        "전일 대비",
    )

    open_price = to_int(
        quote.get("openPriceRaw")
        or quote.get("openPrice"),
        "시가",
    )

    high = to_int(
        quote.get("highPriceRaw")
        or quote.get("highPrice"),
        "고가",
    )

    low = to_int(
        quote.get("lowPriceRaw")
        or quote.get("lowPrice"),
        "저가",
    )

    volume = to_int(
        quote.get("accumulatedTradingVolumeRaw")
        or quote.get("accumulatedTradingVolume"),
        "거래량",
    )

    response_change_rate = to_float(
        quote.get("fluctuationsRatioRaw")
        or quote.get("fluctuationsRatio"),
        "등락률",
    )

    previous, previous_source = get_previous_close(
        session=session,
        current=current,
        change=change,
    )

    # 전일 종가와 공식 등락금액 교차검증
    calculated_change = current - previous

    if calculated_change != change:
        raise RuntimeError(
            "전일 종가 검증 실패\n"
            f"- 현재가: {current}\n"
            f"- 전일 종가: {previous}\n"
            f"- 계산된 등락: {calculated_change}\n"
            f"- 네이버 실시간 등락: {change}\n"
            "서로 일치하지 않아 Firestore 저장을 중단합니다."
        )

    calculated_change_rate = (
        (change / previous) * 100
        if previous > 0
        else 0
    )

    # 소수점 반올림 차이를 감안하여 0.05%p 이내인지 확인
    if abs(calculated_change_rate - response_change_rate) > 0.05:
        raise RuntimeError(
            "등락률 검증 실패\n"
            f"- 계산 등락률: {calculated_change_rate:.4f}%\n"
            f"- 네이버 등락률: {response_change_rate:.4f}%"
        )

    now = now_kst()

    stock_data = {
        "type": "ETF",
        "name": quote.get("stockName") or STOCK_NAME,
        "code": STOCK_CODE,
        "naverUrl": ETF_NAVER_URL,

        "current": current,
        "previous": previous,
        "change": change,
        "changeRate": round(response_change_rate, 4),

        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,

        "market": "한국",
        "marketStatus": quote.get("marketStatus", ""),
        "localTradedAt": quote.get("localTradedAt", ""),

        "source": "NAVER_REALTIME_JSON",
        "previousSource": previous_source,

        "updatedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

    validate_stock_data(stock_data)

    print(
        "최종 수집 데이터:",
        json.dumps(
            {
                key: value
                for key, value in stock_data.items()
                if key != "timestamp"
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    return stock_data


def validate_stock_data(stock_data: dict[str, Any]) -> None:
    """
    잘못된 값이 Firestore에 저장되는 것을 방지합니다.
    """
    current = int(stock_data["current"])
    previous = int(stock_data["previous"])
    change = int(stock_data["change"])
    open_price = int(stock_data["open"])
    high = int(stock_data["high"])
    low = int(stock_data["low"])
    volume = int(stock_data["volume"])

    errors: list[str] = []

    if current <= 0:
        errors.append("현재가가 0 이하입니다.")

    if previous <= 0:
        errors.append("전일 종가가 0 이하입니다.")

    if open_price <= 0:
        errors.append("시가가 0 이하입니다.")

    if high <= 0:
        errors.append("고가가 0 이하입니다.")

    if low <= 0:
        errors.append("저가가 0 이하입니다.")

    if high < low:
        errors.append("고가가 저가보다 낮습니다.")

    if not low <= current <= high:
        errors.append(
            f"현재가 {current}가 "
            f"저가 {low}~고가 {high} 범위 밖입니다."
        )

    if not low <= open_price <= high:
        errors.append(
            f"시가 {open_price}가 "
            f"저가 {low}~고가 {high} 범위 밖입니다."
        )

    if current - previous != change:
        errors.append(
            "현재가 - 전일 종가가 등락금액과 일치하지 않습니다."
        )

    if volume < 0:
        errors.append("거래량이 음수입니다.")

    if previous > 0:
        gap_ratio = abs(current - previous) / previous

        if gap_ratio > 0.30:
            errors.append(
                "현재가와 전일 종가 차이가 30%를 초과합니다."
            )

    if errors:
        message = "\n".join(
            f"- {error}"
            for error in errors
        )

        raise RuntimeError(
            "수집 데이터 검증 실패. "
            "Firestore 저장을 중단합니다.\n"
            + message
        )


# --------------------------------------------------
# Firestore 저장
# --------------------------------------------------

def update_firestore(
    db,
    stock_data: dict[str, Any],
) -> None:
    now = now_kst()

    daily_id = now.strftime("%Y-%m-%d")
    intraday_id = now.strftime("%Y-%m-%d-%H%M")

    stock_ref = (
        db.collection("stocks")
        .document(STOCK_CODE)
    )

    stock_ref.set(
        stock_data,
        merge=True,
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
        "marketStatus": stock_data["marketStatus"],
        "localTradedAt": stock_data["localTradedAt"],
        "source": stock_data["source"],
        "previousSource": stock_data["previousSource"],
        "updatedAt": stock_data["updatedAt"],
        "timestamp": firestore.SERVER_TIMESTAMP,
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
        "marketStatus": stock_data["marketStatus"],
        "localTradedAt": stock_data["localTradedAt"],
        "source": stock_data["source"],
        "previousSource": stock_data["previousSource"],
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

    (
        stock_ref
        .collection("historyIntraday")
        .document(intraday_id)
        .set(intraday_data, merge=True)
    )

    print("Firestore 저장 완료")
    print(f"현재가: {stock_data['current']:,}원")
    print(f"전일가: {stock_data['previous']:,}원")
    print(f"등락: {stock_data['change']:+,}원")
    print(f"등락률: {stock_data['changeRate']:+.2f}%")
    print(f"시가: {stock_data['open']:,}원")
    print(f"고가: {stock_data['high']:,}원")
    print(f"저가: {stock_data['low']:,}원")
    print(f"거래량: {stock_data['volume']:,}주")


# --------------------------------------------------
# 실행
# --------------------------------------------------

def main() -> None:
    print("ETF 데이터 업데이트 시작")

    db = init_firestore()
    print("Firestore 연결 성공")

    session = create_http_session()
    stock_data = build_stock_data(session)

    print("네이버 실시간 JSON 데이터 수집 성공")

    update_firestore(db, stock_data)

    print("ETF 데이터 업데이트 완료")


if __name__ == "__main__":
    main()