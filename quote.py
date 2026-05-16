"""Yahoo Finance v8 chart 엔드포인트로 '직전에 완료된 정규장' 종가·등락률 조회.

봇은 KST 04:30(= 미 동부 EDT 15:30, 즉 미국 정규장 진행 중)에 실행되므로
`meta.regularMarketPrice`를 그대로 쓰면 장중가 또는 시간외 가격이 표시된다.
대신 일별 OHLC 시계열(`indicators.quote[0].close`)에서 미완료 봉을 걸러내고
가장 최근 두 개의 '완료된 정규장 종가'를 비교한다.
"""

import logging
import requests

log = logging.getLogger("quote")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 마지막 일봉을 '미완료'로 보고 제외해야 하는 상태들.
# REGULAR: 정규장 진행 중, PRE: 장전 (오늘 봉이 아직 생성 중이거나 직전 거래일 미마감 데이터)
_INCOMPLETE_STATES = {"REGULAR", "PRE"}


def fetch_quote(ticker: str) -> dict | None:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        "?interval=1d&range=10d"
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        meta = result["meta"]
        market_state = meta.get("marketState", "")

        timestamps = result.get("timestamp") or []
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        valid = [(ts, c) for ts, c in zip(timestamps, closes) if c is not None]

        if market_state in _INCOMPLETE_STATES and valid:
            valid = valid[:-1]

        if len(valid) < 2:
            log.warning("Quote: %s 완료된 거래일 데이터 부족 (state=%s)", ticker, market_state)
            return None

        price = float(valid[-1][1])
        prev_close = float(valid[-2][1])
        return {
            "ticker": ticker,
            "price": price,
            "prev_close": prev_close,
            "change_pct": (price - prev_close) / prev_close * 100,
            "currency": meta.get("currency", "USD"),
        }
    except Exception as e:
        log.warning("Quote fetch failed for %s: %s", ticker, e)
        return None
