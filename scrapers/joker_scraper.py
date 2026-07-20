"""Joker (Greek OPAP/Allwyn lottery) scraper.

See scrapers/_allwyn_common.py for the shared parsing logic and its
caveats (annuity-style prize tiers, bot-protected site requiring Playwright).
"""
from scrapers._allwyn_common import fetch_latest_draw

URL = "https://www.allwyn.gr/el/tzoker/draws-results"


def fetch_draw() -> dict:
    return fetch_latest_draw(game="joker", url=URL)


if __name__ == "__main__":
    print(fetch_draw())
