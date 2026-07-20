"""Entrypoint run on a schedule by .github/workflows/scrape.yml.

Scrapes the latest Eurojackpot, Joker and Lotto draw and upserts each into
data/lottery.db. Eurojackpot tries the reverse-engineered API first and
only falls back to Playwright if that call fails; Joker/Lotto go straight
to Playwright since allwyn.gr has no equivalent API (see
scrapers/_allwyn_common.py).
"""
import sys
from pathlib import Path

from db.repository import DB_PATH, connect, export_draws_csv, init_db, upsert_draw
from scrapers import joker_scraper, lotto_scraper
from scrapers.eurojackpot_api import EurojackpotApiError, fetch_draw as fetch_eurojackpot_api

CSV_EXPORT_PATH = DB_PATH.parent / "draws_export.csv"


def scrape_eurojackpot() -> dict:
    try:
        return fetch_eurojackpot_api()
    except EurojackpotApiError as exc:
        print(f"[eurojackpot] API failed ({exc}); falling back to Playwright", file=sys.stderr)
        from scrapers.eurojackpot_playwright import fetch_draw as fetch_eurojackpot_playwright
        return fetch_eurojackpot_playwright()


SCRAPERS = {
    "eurojackpot": scrape_eurojackpot,
    "joker": joker_scraper.fetch_draw,
    "lotto": lotto_scraper.fetch_draw,
}


def main() -> None:
    init_db()
    with connect() as conn:
        for game, scrape in SCRAPERS.items():
            try:
                draw = scrape()
            except Exception as exc:
                print(f"[{game}] scrape failed: {exc}", file=sys.stderr)
                continue

            upsert_draw(
                conn,
                game=draw["game"],
                draw_date=draw["draw_date"],
                stakes_eur=draw["stakes_eur"],
                total_payout_eur=draw["total_payout_eur"],
                profit_eur=draw["profit_eur"],
                winning_numbers=draw["winning_numbers"],
                source=draw["source"],
                prize_tiers=draw.get("prize_tiers"),
            )
            print(f"[{game}] upserted draw {draw['draw_date']} (source={draw['source']})")

        export_draws_csv(conn, CSV_EXPORT_PATH)


if __name__ == "__main__":
    main()
