"""Yahoo Finance v8 chart 엔드포인트로 현재가·전일종가·등락률 조회."""

import logging
import requests

log = logging.getLogger("quote")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_quote(ticker: str) -> dict | None:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        "?interval=1d&range=5d"
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None or not prev_close:
            return None
        return {
            "ticker": ticker,
            "price": float(price),
            "prev_close": float(prev_close),
            "change_pct": (float(price) - float(prev_close)) / float(prev_close) * 100,
            "currency": meta.get("currency", "USD"),
        }
    except Exception as e:
        log.warning("Quote fetch failed for %s: %s", ticker, e)
        return None
