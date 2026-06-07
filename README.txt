# 주식 모니터링 상세페이지 버전

## 추가된 기능
1. 메인 화면에서 ETF 또는 구성종목 행 클릭
2. detail.html 상세페이지로 이동
3. 현재가, 전일, 등락률, 거래량 표시
4. 날짜별 누적 데이터 표 표시
5. 종가기준 미니차트 표시

## 실행 방법
압축을 풀고 index.html을 더블클릭하세요.

## 다음 단계 Firestore 구조
stocks/{종목코드}
- name
- code
- current
- previous
- open
- high
- low
- volume
- market
- weight

stocks/{종목코드}/history/{YYYY-MM-DD}
- date
- close
- volume
- open
- high
- low
