"""Playwright fallback scraper for eurojackpot.com.

Only used when scrapers.eurojackpot_api fails (endpoint down or its JSON
shape changed). Scrapes the same public page the old Selenium script
used, but only the *current* draw -- there's no reliable way to pick an
arbitrary historical date through the UI, so this path can't backfill.
"""
import re

from playwright.sync_api import sync_playwright

URL = "https://www.eurojackpot.com/"


class EurojackpotPlaywrightError(Exception):
    """Raised when the page structure doesn't match what we expect."""


def fetch_draw() -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(URL, wait_until="networkidle", timeout=30_000)
            body_text = page.locator("body").inner_text()
            stakes_eur = _extract_stakes(body_text)
            prize_tiers, total_payout_eur = _extract_payout(body_text)
            draw_date = _extract_date(page)
        finally:
            browser.close()

    profit_eur = (stakes_eur - total_payout_eur) if stakes_eur is not None else None
    return {
        "game": "eurojackpot",
        "draw_date": draw_date,
        "stakes_eur": stakes_eur,
        "total_payout_eur": total_payout_eur,
        "profit_eur": profit_eur,
        "winning_numbers": None,  # not extracted in the fallback path; see module docstring
        "source": "playwright",
        "prize_tiers": prize_tiers,
    }


def _extract_stakes(body_text: str) -> float:
    match = re.search(r"Stakes:\s*€\s*([\d,]+\.\d+)", body_text)
    if not match:
        raise EurojackpotPlaywrightError("Could not find a 'Stakes: €...' figure on the page")
    return float(match.group(1).replace(",", ""))


def _extract_payout(body_text: str) -> tuple[list[dict], float]:
    # Each prize-breakdown row renders as e.g.
    # "2\n\t\nMatch 5 + 1 Euro number\n\t6 ×\t€334,966.50\n\n"
    rows = re.findall(
        r"(\d+)\n\t\n([^\n]+)\n\t([\d,]+)\s*×\t(not hit|€[\d,]+\.\d+)",
        body_text,
    )
    if not rows:
        raise EurojackpotPlaywrightError("Could not find the prize-breakdown table on the page")

    prize_tiers = []
    total_payout = 0.0
    for tier_class, description, winners_raw, prize_raw in rows:
        winners = int(winners_raw.replace(",", ""))
        prize = 0.0 if prize_raw == "not hit" else float(prize_raw.lstrip("€").replace(",", ""))
        total_payout += winners * prize
        prize_tiers.append({
            "tier_class": int(tier_class),
            "description": description.strip(),
            "winners_count": winners,
            "prize_amount": prize,
            "jackpot_amount": None,
        })
    return prize_tiers, total_payout


def _extract_date(page) -> str:
    # The <select>'s current value is already ISO (e.g. "2026-07-17"), unlike
    # its display text ("Friday, 17.07.2026"). Angular manages selection via
    # JS rather than the HTML `selected` attribute, so read the live value
    # (input_value) instead of querying for option[selected].
    value = page.locator("select[formcontrolname='datum']").input_value()
    if not value:
        raise EurojackpotPlaywrightError("Could not find the draw-date selector on the page")
    return value


if __name__ == "__main__":
    print(fetch_draw())
