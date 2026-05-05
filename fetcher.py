"""Google News RSS — KST 어제 00:00 ~ 23:59 사이 게재된 뉴스만."""

import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote_plus

import feedparser
import requests

log = logging.getLogger("fetcher")

_TAG_RE = re.compile(r"<[^>]+>")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

KST = timezone(timedelta(hours=9))


def _strip_html(s: str) -> str:
    return unescape(_TAG_RE.sub("", s or "")).strip()


def yesterday_window_utc() -> tuple[datetime, datetime]:
    now_kst = datetime.now(KST)
    today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    yest_start_kst = today_start_kst - timedelta(days=1)
    return yest_start_kst.astimezone(timezone.utc), today_start_kst.astimezone(timezone.utc)


def fetch_yesterday_news(
    query: str,
    lang: str = "ko",
    country: str = "KR",
    max_items: int = 30,
) -> list[dict]:
    start, end = yesterday_window_utc()
    # when:2d로 폭 넓게 받고 KST 어제 윈도로 다시 잘라냄 (RSS 시각 정밀도 보정)
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}+when:2d&hl={lang}&gl={country}&ceid={country}:{lang}"
    )

    try:
        r = requests.get(url, timeout=15, headers=_HEADERS)
        r.raise_for_status()
    except Exception as e:
        log.error("Google News fetch failed (%s): %s", query, e)
        return []

    parsed = feedparser.parse(r.content)
    items: list[dict] = []
    for entry in parsed.entries:
        try:
            pub_date = parsedate_to_datetime(getattr(entry, "published", ""))
        except Exception:
            continue
        if pub_date < start or pub_date >= end:
            continue

        link = getattr(entry, "link", "") or ""
        if not link:
            continue

        desc = _strip_html(getattr(entry, "summary", "") or "")
        src_name = ""
        try:
            src = getattr(entry, "source", None)
            if src and getattr(src, "title", None):
                src_name = src.title
        except Exception:
            pass

        items.append({
            "title": _strip_html(entry.title),
            "description": desc,
            "link": link,
            "source": src_name,
            "pub_date": pub_date.astimezone(timezone.utc).isoformat(),
        })
        if len(items) >= max_items:
            break

    log.info("[%s] yesterday=%d items (%s/%s)", query, len(items), lang, country)
    return items


def fetch_yesterday_news_multi(query: str, max_per_source: int = 20) -> list[dict]:
    """한국·해외 소스를 모두 받아 link 기준 dedup. origin 배지 부여."""
    sources = [
        ("ko", "KR", "🇰🇷"),
        ("en", "US", "🌐"),
    ]
    seen: set[str] = set()
    merged: list[dict] = []
    for lang, country, badge in sources:
        for it in fetch_yesterday_news(query, lang=lang, country=country, max_items=max_per_source):
            link = it.get("link", "")
            if not link or link in seen:
                continue
            seen.add(link)
            it["origin"] = badge
            merged.append(it)
    merged.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
    log.info("[%s] multi=%d items (dedup)", query, len(merged))
    return merged
