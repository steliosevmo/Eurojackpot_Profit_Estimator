"""Reverse-engineered JSON API client for eurojackpot.com.

The public site's Angular frontend calls this endpoint directly
(`wlinfo/WL_InfoService`) to render numbers/odds. It accepts a `datum`
(draw date) and returns stakes, the full prize-tier breakdown, winning
numbers, and (via the `jahr` param) a list of that calendar year's draw
dates -- which is what `pipeline/backfill_history.py` uses to enumerate
every historical draw since 2012.

This is the primary scraping path. If the endpoint's shape ever changes
or the call fails, `scrapers/eurojackpot_playwright.py` is the fallback.
"""
from datetime import date

import requests

BASE_URL = "https://www.eurojackpot.com/wlinfo/WL_InfoService"
COMMON_PARAMS = {
    "client": "jsn",
    "gruppe": "ZahlenUndQuoten",
    "ewGewsum": "ja",
    "historie": "ja",
    "spielart": "EJ",
    "adg": "ja",
    "lang": "en",
}
TIMEOUT_SECONDS = 15


class EurojackpotApiError(Exception):
    """Raised when the API call fails or returns an unexpected shape."""


def _get(params: dict) -> dict:
    try:
        response = requests.get(BASE_URL, params={**COMMON_PARAMS, **params}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise EurojackpotApiError(str(exc)) from exc

    if payload.get("error"):
        raise EurojackpotApiError(payload["error"])
    return payload


def fetch_draw(draw_date: str | None = None) -> dict:
    """Fetch and normalize a single draw. `draw_date` is 'YYYY-MM-DD'; omit for the latest."""
    params = {"datum": draw_date} if draw_date else {}
    payload = _get(params)
    return _normalize(payload)


def list_year_draw_dates(year: int) -> list[str]:
    """Return every Eurojackpot draw date the API knows about for `year`."""
    payload = _get({"jahr": year, "datum": f"{year}-06-15"})
    tage = payload.get("history", {}).get("tage", [])
    return sorted(d for d in tage if d.startswith(str(year)))


def known_years() -> list[int]:
    payload = _get({})
    return sorted(payload.get("history", {}).get("jahre", []))


def _normalize(payload: dict) -> dict:
    head = payload["head"]
    draw_date = head["datum"]

    main_numbers, euro_numbers = [], []
    for group in payload["zahlen"]["hauptlotterie"]["ziehungen"]:
        if group["bezeichnung"] == "5 of 50":
            main_numbers = [int(n) for n in group["zahlenSortiert"]]
        elif group["bezeichnung"] == "2 of 12":
            euro_numbers = [int(n) for n in group["zahlenSortiert"]]

    stakes_eur = payload["auswertung"]["spieleinsatz"]["hauptlotterie"]

    tiers = payload["auswertung"]["quoten"]["hauptlotterie"]["ziehungen"][0]["gewinnklassen"]
    prize_tiers = []
    total_payout_eur = 0.0
    for tier in tiers:
        winners = tier["anzahl"] or 0
        prize = tier["quote"] or 0.0
        total_payout_eur += winners * prize
        prize_tiers.append({
            "tier_class": tier["klasse"],
            "description": tier["beschreibung"],
            "winners_count": winners,
            "prize_amount": prize,
            "jackpot_amount": tier.get("jackpot"),
        })

    profit_eur = (stakes_eur - total_payout_eur) if stakes_eur is not None else None

    return {
        "game": "eurojackpot",
        "draw_date": draw_date,
        "stakes_eur": stakes_eur,
        "total_payout_eur": total_payout_eur,
        "profit_eur": profit_eur,
        "winning_numbers": {"main": main_numbers, "euro": euro_numbers},
        "source": "api",
        "prize_tiers": prize_tiers,
    }


if __name__ == "__main__":
    print(fetch_draw())
