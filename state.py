"""기업별 최근 게시 제목 누적 저장 — 다음 호출에서 같은 사건 재게시 회피용."""

import json
import logging
from config import STATE_FILE

log = logging.getLogger("state")

KEEP_LAST_N = 30


def load() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("state load failed: %s", e)
        return {}


def save(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("state save failed: %s", e)


def recent_titles(state: dict, company: str) -> list[str]:
    return state.get(company, {}).get("recent_titles", [])


def update(state: dict, company: str, new_titles: list[str]) -> dict:
    prior = state.get(company, {}).get("recent_titles", [])
    merged = list(new_titles) + prior
    seen: set[str] = set()
    deduped: list[str] = []
    for t in merged:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
        if len(deduped) >= KEEP_LAST_N:
            break
    state[company] = {"recent_titles": deduped}
    return state
