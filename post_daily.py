"""매일 7시 cron이 호출하는 비대화형 entry.

companies.json의 모든 기업에 대해 어제(KST 기준) 게재된 Google News를 모아
Claude Haiku 4.5로 선별·2줄 요약 후 텔레그램 채널에 게시.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from html import escape

from config import COMPANIES_FILE
from fetcher import fetch_yesterday_news_multi
from quote import fetch_quote
import state as state_store
from summarizer import summarize
from telegram_post import send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("post_daily")

KST = timezone(timedelta(hours=9))
INTER_COMPANY_DELAY_SEC = 2


def _yesterday_str() -> str:
    return (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d (%a)")


def _quote_line(ticker: str) -> str:
    if not ticker:
        return ""
    q = fetch_quote(ticker)
    if not q:
        return ""
    pct = q["change_pct"]
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "─")
    sign = "+" if pct > 0 else ""
    sym = "$" if q["currency"] == "USD" else f"{q['currency']} "
    chart_url = f"https://www.tradingview.com/symbols/{ticker}/"
    return (
        f'{sym}{q["price"]:,.2f}  {arrow} {sign}{pct:.2f}%  '
        f'· <a href="{escape(chart_url)}">📈 차트 보기</a>'
    )


_TIER_BADGE = {"high": "🔴", "medium": "🟡"}


def _format(entry: dict, items: list[dict], summaries: list[dict]) -> tuple[str, list[str]]:
    name = entry["name"]
    ticker = entry.get("ticker", "")
    by_idx: dict[int, dict] = {}
    for s in summaries:
        if "index" in s:
            by_idx[s["index"]] = s
    selected = [(i, items[i]) for i in by_idx.keys() if 0 <= i < len(items)]
    if not selected:
        return "", []

    title_line = f"📰 <b>{escape(name)}</b>"
    if ticker:
        title_line += f" ({escape(ticker)})"
    title_line += f" · {_yesterday_str()}"

    qline = _quote_line(ticker)
    header = title_line + (f"\n{qline}" if qline else "") + "\n─────────────────"
    body = []
    posted_titles: list[str] = []
    for n, (idx, c) in enumerate(selected, 1):
        raw_title = c.get("title", "(제목 없음)")
        posted_titles.append(raw_title)
        title = escape(raw_title)
        link = c.get("link", "")
        src = c.get("source", "")
        origin = c.get("origin", "")
        meta_obj = by_idx[idx]
        summ = escape((meta_obj.get("summary") or "").strip())
        tier = meta_obj.get("tier", "medium")
        tier_badge = _TIER_BADGE.get(tier, "🟡")
        if tier == "high":
            head_line = f"{tier_badge} <b>{n}. {title}</b>"
        else:
            head_line = f"{tier_badge} {n}. {title}"
        badge = f"{origin} " if origin else ""
        meta = f"{badge}<i>{escape(src)}</i> · " if src else badge
        body.append(
            f"{head_line}\n"
            f"{summ}\n"
            f'{meta}<a href="{escape(link)}">🔗 원문 보기</a>'
        )
    return header + "\n\n" + "\n\n".join(body), posted_titles


def run():
    with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
        companies = json.load(f)

    if not companies:
        log.warning("companies.json 비어있음 — 등록된 기업 없음.")
        return

    state = state_store.load()
    posted = skipped = failed = 0
    for entry in companies:
        name = entry["name"]
        query = entry.get("query") or name
        try:
            items = fetch_yesterday_news_multi(query)
            if not items:
                log.info("[%s] 어제 뉴스 0건, skip", name)
                skipped += 1
                continue
            prior = state_store.recent_titles(state, name)
            summaries = summarize(items, name, prior_titles=prior)
            msg, posted_titles = _format(entry, items, summaries)
            if not msg:
                log.info("[%s] 요약된 기사 0건, skip", name)
                skipped += 1
                continue
            send(msg)
            log.info("[%s] 게시 완료 (%d/%d)", name, len(summaries), len(items))
            state = state_store.update(state, name, posted_titles)
            state_store.save(state)
            posted += 1
            time.sleep(INTER_COMPANY_DELAY_SEC)
        except Exception as e:
            log.exception("[%s] 처리 실패", name)
            failed += 1
            try:
                send(f"⚠️ <b>{escape(name)}</b> 처리 실패: <code>{escape(str(e)[:200])}</code>")
            except Exception:
                pass

    log.info("종료: posted=%d skipped=%d failed=%d", posted, skipped, failed)


if __name__ == "__main__":
    run()
