"""기업당 뉴스 묶음을 Claude Haiku 한 번 호출로 선별 + 2줄 요약."""

import logging
import time
import anthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

log = logging.getLogger("summarizer")
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=0)

MAX_ATTEMPTS = 3
WAIT = 30
MAX_ARTICLES = 30
MAX_OUTPUT = 5

SYSTEM_PROMPT = """한국 투자자를 위한 뉴스 큐레이터. 주어진 어제자 기사들 중 투자 판단에 도움되는 것만 골라낸다.

다음 카테고리를 우선순위로 (위에 있을수록 중요):
1. 실적·가이던스·매출 발표
2. 신제품 출시·기존 제품 단종·생산 변경
3. 규제·소송·정부 정책
4. 대형 계약·M&A·자본조달·자사주 매입·배당
5. 임원 변경·주요 인사
6. 기업에 직접 영향 미치는 거시 이벤트 (관세·금리·산업 정책)

선별 기준:
- 같은 사건 다중 보도 → 정보량 가장 많은 1건만
- 단순 시황·주가 등락·차트 분석 기사 제외
- 광고·홍보·연예성 기사 제외
- "최근 게시된 제목"으로 제공된 사건과 동일·유사 사건은 제외 (재탕 금지)

출력 개수:
- 최대 5건
- 정말 중요한 게 1건이면 1건만 내도 됨
- 5건 채우려고 노이즈 끼우지 말 것 — 부족한 게 정상

티어 부여:
- high: 주가·실적·전략에 직접 충격 (실적, 대형 계약, 규제·소송, M&A, 정책 변경)
- medium: 보조·정성 정보 (전망 코멘트, 부분 트렌드, 임원 인터뷰)

기사 요약 규칙:
- 정확히 2줄
- 각 줄 100자 이내
- 정량 정보(숫자·당사자·시점) 우선 보존
- 평어체, 군더더기 없이

반드시 select_and_summarize 도구를 호출해 결과 반환."""

TOOL = {
    "name": "select_and_summarize",
    "description": "투자 관점 중요 기사만 최대 5건 골라 tier·2줄 요약 부여.",
    "input_schema": {
        "type": "object",
        "properties": {
            "articles": {
                "type": "array",
                "maxItems": MAX_OUTPUT,
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {
                            "type": "integer",
                            "description": "후보 목록의 0-based 인덱스",
                        },
                        "tier": {
                            "type": "string",
                            "enum": ["high", "medium"],
                            "description": "high=주가/실적 직접 충격, medium=보조 정보",
                        },
                        "summary": {
                            "type": "string",
                            "description": "정확히 2줄, 각 줄 100자 이내",
                        },
                    },
                    "required": ["index", "tier", "summary"],
                },
            },
        },
        "required": ["articles"],
    },
}


def _build_block(items: list[dict]) -> str:
    rows = []
    for i, c in enumerate(items):
        title = c.get("title", "")
        desc = (c.get("description") or "")[:240]
        rows.append(f"[{i}] {title}\n    {desc}")
    return "\n\n".join(rows)


def summarize(items: list[dict], company: str, prior_titles: list[str] | None = None) -> list[dict]:
    if not items:
        return []
    items = items[:MAX_ARTICLES]

    prior_block = ""
    if prior_titles:
        joined = "\n".join(f"- {t}" for t in prior_titles[:30])
        prior_block = (
            f"\n\n--- 최근 게시된 제목 (재탕 금지 대상) ---\n{joined}\n--- 끝 ---"
        )

    user_prompt = (
        f"기업: {company}\n"
        f"어제 게재된 후보 기사 {len(items)}건. "
        f"투자 관점 중요 기사만 최대 5건 골라 tier·2줄 요약 부여, select_and_summarize 호출.\n"
        f"{prior_block}\n\n"
        f"--- 후보 시작 ---\n{_build_block(items)}\n--- 후보 끝 ---"
    )

    payload = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "select_and_summarize"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = _client.messages.create(**payload)
            log.info(
                "[%s] stop=%s in=%s out=%s",
                company,
                resp.stop_reason,
                getattr(resp.usage, "input_tokens", "?"),
                getattr(resp.usage, "output_tokens", "?"),
            )
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "select_and_summarize":
                    return block.input.get("articles", []) or []
            raise RuntimeError(f"select_and_summarize 응답 없음 (stop={resp.stop_reason})")
        except anthropic.RateLimitError as e:
            last_err = e
            log.warning("rate limited, sleep %ds (attempt %d/%d)", WAIT, attempt, MAX_ATTEMPTS)
            time.sleep(WAIT)

    raise last_err if last_err else RuntimeError("summarize: unknown failure")
