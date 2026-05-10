"""Yahoo Finance v8 chart 엔드포인트로 현재가·전일종가·등락률 조회.

`includePrePost=true`로 분봉을 받아 마지막 데이터 시각이 정규장 종가 시각(regularMarketTime)보다
뒤면 extended hours(시간외/장전)로 판정해 표시 가격을 바꾼다.
- 정규장: regularMarketPrice vs chartPreviousClose
- 시간외(post): 마지막 분봉 close vs regularMarketPrice (당일 정규장 종가 대비)
  └ regularMarketTime + 4.5시간 이내인 경우 (extended hours는 정규장 종료 후 4시간)
- 장전(pre): 마지막 분봉 close vs regularMarketPrice (직전 정규장=전일 종가 대비)
  └ regularMarketTime + 4.5시간 초과 (= 다음 거래일 pre-market)
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

_POST_WINDOW_SEC = 4.5 * 3600  # 정규장 종료 후 시간외 거래 창 (실제 4시간 + 30분 버퍼)


def fetch_quote(ticker: str) -> dict | None:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        "?interval=1m&range=1d&includePrePost=true"
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        meta = result["meta"]
        regular_price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        regular_time = meta.get("regularMarketTime")
        if regular_price is None or not prev_close:
            return None

        # 기본: 정규장 시세
        price = float(regular_price)
        base = float(prev_close)
        session = "regular"

        # 분봉 시계열 마지막 non-null close 시각으로 시간외/장전 감지
        timestamps = result.get("timestamp") or []
        quote_block = (result.get("indicators", {}).get("quote") or [{}])[0]
        closes = quote_block.get("close") or []
        last_idx = next(
            (i for i in range(len(closes) - 1, -1, -1) if closes[i] is not None),
            None,
        )

        if (
            last_idx is not None
            and regular_time
            and last_idx < len(timestamps)
            and timestamps[last_idx] > regular_time + 60  # 정규장 종가보다 1분 이상 뒤
        ):
            extended_price = float(closes[last_idx])
            delta_sec = timestamps[last_idx] - regular_time
            if delta_sec <= _POST_WINDOW_SEC:
                # 정규장 종료 후 시간외 거래 (당일 종가 대비)
                price = extended_price
                base = float(regular_price)
                session = "post"
            else:
                # 다음 거래일 장전 (직전 정규장 종가=전일 종가 대비)
                price = extended_price
                base = float(regular_price)
                session = "pre"

        return {
            "ticker": ticker,
            "price": price,
            "prev_close": base,
            "change_pct": (price - base) / base * 100,
            "currency": meta.get("currency", "USD"),
            "session": session,
        }
    except Exception as e:
        log.warning("Quote fetch failed for %s: %s", ticker, e)
        return None
