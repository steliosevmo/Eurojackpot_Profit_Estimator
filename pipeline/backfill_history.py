"""One-off script: backfill every historical Eurojackpot draw since 2012.

Uses scrapers.eurojackpot_api's `jahr` parameter to enumerate each year's
draw dates, then fetches and upserts any date not already in the DB.

NOTE: Joker/Lotto are NOT backfilled here. allwyn.gr's draws-results pages
only expose the *current* draw without JavaScript-driven form interaction
(see scrapers/_allwyn_common.py); historical Joker/Lotto data starts
accumulating only from whenever pipeline/scrape_latest.py starts running
on a schedule. Driving the site's year/month/draw-number search form to
backfill those two games is a reasonable follow-up, not implemented here.
"""
import sys
import time

from db.repository import connect, draw_exists, init_db, upsert_draw
from scrapers.eurojackpot_api import EurojackpotApiError, fetch_draw, known_years, list_year_draw_dates

REQUEST_DELAY_SECONDS = 0.5


def main() -> None:
    init_db()
    with connect() as conn:
        for year in known_years():
            for draw_date in list_year_draw_dates(year):
                if draw_exists(conn, game="eurojackpot", draw_date=draw_date):
                    continue
                try:
                    draw = fetch_draw(draw_date)
                except EurojackpotApiError as exc:
                    print(f"skipped {draw_date}: {exc}", file=sys.stderr)
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
                    prize_tiers=draw["prize_tiers"],
                )
                print(f"backfilled {draw_date}")
                time.sleep(REQUEST_DELAY_SECONDS)


if __name__ == "__main__":
    main()
