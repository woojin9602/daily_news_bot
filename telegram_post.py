"""채널에 sendMessage. 4090자 자동 분할."""

import logging
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

log = logging.getLogger("telegram")
TG_LIMIT = 4090
API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def split_text(text: str, limit: int = TG_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        cand = (buf + "\n\n" + para) if buf else para
        if len(cand) <= limit:
            buf = cand
        else:
            if buf:
                chunks.append(buf)
            if len(para) <= limit:
                buf = para
            else:
                for i in range(0, len(para), limit):
                    chunks.append(para[i : i + limit])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def send(text: str) -> None:
    for chunk in split_text(text):
        r = requests.post(
            f"{API}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            },
            timeout=20,
        )
        if not r.ok:
            log.error("Telegram send failed: %s %s", r.status_code, r.text[:300])
        r.raise_for_status()
