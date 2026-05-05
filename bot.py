"""기업 추가/삭제/즉시 실행 메뉴.

매일 7시 cron이 호출하는 entry는 post_daily.py 쪽이고, 이 파일은 사용자가
수동으로 기업 목록을 관리하거나 즉시 한 번 실행할 때 쓰는 인터랙티브 CLI.
"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "companies.json"


def load() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save(companies: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(companies, f, ensure_ascii=False, indent=2)


def show_menu() -> None:
    print("\n========== 데일리 뉴스 봇 ==========")
    print("1. 기업 목록 보기")
    print("2. 기업 추가")
    print("3. 기업 삭제")
    print("4. 지금 한 번 실행 (어제 뉴스 게시)")
    print("5. 종료")


def list_companies(companies: list[dict]) -> None:
    if not companies:
        print("(등록된 기업 없음)")
        return
    for i, c in enumerate(companies, 1):
        q = c.get("query", "")
        ticker = c.get("ticker", "")
        parts = []
        if q and q != c["name"]:
            parts.append(f"검색어: {q}")
        if ticker:
            parts.append(f"티커: {ticker}")
        extra = f"  [{' · '.join(parts)}]" if parts else ""
        print(f"{i}. {c['name']}{extra}")


def add_company(companies: list[dict]) -> None:
    name = input("기업명: ").strip()
    if not name:
        print("취소.")
        return
    query = input("검색어 (Enter=기업명 그대로): ").strip() or name
    ticker = input("티커 (Enter=시세 미표시, 예: TSLA): ").strip().upper()
    item = {"name": name, "query": query}
    if ticker:
        item["ticker"] = ticker
    companies.append(item)
    save(companies)
    suffix = f" / {ticker}" if ticker else ""
    print(f"추가됨: {name}{suffix}")


def remove_company(companies: list[dict]) -> None:
    if not companies:
        print("(등록된 기업 없음)")
        return
    list_companies(companies)
    raw = input("삭제할 번호: ").strip()
    try:
        idx = int(raw) - 1
    except ValueError:
        print("숫자 입력 필요.")
        return
    if 0 <= idx < len(companies):
        removed = companies.pop(idx)
        save(companies)
        print(f"삭제됨: {removed['name']}")
    else:
        print("잘못된 번호.")


def run_now() -> None:
    print("실행 중... 로그가 출력됩니다.\n")
    from post_daily import run
    run()


def main() -> None:
    companies = load()
    while True:
        show_menu()
        choice = input("메뉴 번호: ").strip()
        if choice == "1":
            list_companies(companies)
        elif choice == "2":
            add_company(companies)
        elif choice == "3":
            remove_company(companies)
            companies = load()
        elif choice == "4":
            run_now()
        elif choice == "5":
            break
        else:
            print("잘못된 입력.")


if __name__ == "__main__":
    main()
