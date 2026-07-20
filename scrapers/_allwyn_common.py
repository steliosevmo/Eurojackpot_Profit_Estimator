"""Shared Playwright scraping/parsing logic for allwyn.gr's Joker and Lotto results pages.

allwyn.gr (OPAP's retail site, rebranded under parent company Allwyn) returns
403 Forbidden to plain HTTP clients (bot protection), so unlike Eurojackpot
there is no usable reverse-engineered API here -- a real browser is required.

Each game's "draws-results" page renders the latest draw's total columns
played ("Sigma Stiles" -- Greek Joker/Lotto tickets are EUR 1/column, so
this is a genuine stakes figure) plus a full prize-tier table, e.g.:

    Katigoria   Katanemomena   Epitychies   Kerdi ana epitychia
    5+1         1.000.000,00   -            TZAKPOT
    5                          1            100.000,00
    ...

Some tiers pay an annuity ("10.000EUR kathe mina gia 10 chronia") instead of
a flat amount; those can't be summed into total_payout_eur cleanly, so they
are recorded with prize_amount=None and kept in `description` for reference.
This means total_payout_eur (and therefore profit_eur) is a best-effort
under-estimate for draws with an annuity winner -- stakes_eur is the more
reliable revenue signal for these two games.
"""
import re
from datetime import datetime

from playwright.sync_api import sync_playwright

TICKET_PRICE_EUR = 1.0

_GREEK_MONTHS = {
    "ιανουαρίου": 1, "φεβρουαρίου": 2, "μαρτίου": 3, "απριλίου": 4,
    "μαΐου": 5, "ιουνίου": 6, "ιουλίου": 7, "αυγούστου": 8,
    "σεπτεμβρίου": 9, "οκτωβρίου": 10, "νοεμβρίου": 11, "δεκεμβρίου": 12,
}


class AllwynScrapeError(Exception):
    """Raised when the page text doesn't match the expected shape."""


def _parse_greek_number(text: str) -> float:
    """'1.241.793' -> 1241793.0, '100.000,00' -> 100000.0"""
    return float(text.replace(".", "").replace(",", "."))


def _parse_date(raw: str) -> str:
    raw = raw.strip()
    slash_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
    if slash_match:
        day, month, year = slash_match.groups()
        return f"{year}-{month}-{day}"

    words = raw.lower().split()
    for i, word in enumerate(words):
        if word in _GREEK_MONTHS and i >= 1 and i + 1 < len(words):
            day = re.sub(r"\D", "", words[i - 1])
            year = re.sub(r"\D", "", words[i + 1])
            if day and year:
                return f"{year}-{_GREEK_MONTHS[word]:02d}-{int(day):02d}"
    raise AllwynScrapeError(f"Could not parse a date out of: {raw!r}")


def fetch_latest_draw(*, game: str, url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            body_text = page.locator("body").inner_text()
        finally:
            browser.close()
    return _parse_draw_text(body_text, game=game)


def _parse_draw_text(text: str, *, game: str) -> dict:
    draw_match = re.search(r"Κλήρωση:?\s*(\d+)", text)
    date_match = re.search(r"Ημερομηνία:?\s*([^\n]*?Σύνολο Στηλών|[^\n]+)", text)
    columns_match = re.search(r"Σύνολο Στηλών\s*([\d.]+)", text)
    if not (draw_match and columns_match):
        raise AllwynScrapeError(f"Unexpected page shape for {game}; couldn't find draw/columns")

    draw_number = draw_match.group(1)
    total_columns = _parse_greek_number(columns_match.group(1))
    stakes_eur = total_columns * TICKET_PRICE_EUR

    date_fragment = date_match.group(1).replace("Σύνολο Στηλών", "") if date_match else ""
    draw_date = _parse_date(date_fragment)

    winning_numbers = []
    if "Αποτελέσματα Κλήρωσης" in text:
        after = text[text.index("Αποτελέσματα Κλήρωσης") + len("Αποτελέσματα Κλήρωσης"):]
        for line in after.splitlines():
            line = line.strip()
            if not line:
                continue
            if not re.fullmatch(r"[\d\s]+", line):
                break
            winning_numbers.extend(int(n) for n in line.split())

    if "Κατηγορία" not in text:
        raise AllwynScrapeError(f"Unexpected page shape for {game}; couldn't find the prize-tier table")

    # Table rows come out of innerText as tab-separated cells, one row per line
    # (e.g. Joker: "category\tdistributed\twinners\tprize", Lotto has no
    # "distributed" column: "category\twinners\tprize").
    lines = text[text.index("Κατηγορία"):].splitlines()
    header_cells = lines[0].split("\t")
    has_distributed_column = any("Διανεμόμενα" in c for c in header_cells)
    category_pattern = re.compile(r"^\d[\d+]*$")

    prize_tiers = []
    total_payout_eur = 0.0
    tier_index = 0
    for line in lines[1:]:
        cells = line.split("\t")
        if not cells or not category_pattern.match(cells[0].strip()):
            break

        category = cells[0].strip()
        if has_distributed_column:
            distributed_raw, winners_raw, prize_raw = (cells + ["", "", ""])[1:4]
        else:
            distributed_raw = ""
            winners_raw, prize_raw = (cells + ["", ""])[1:3]

        winners = 0 if winners_raw.strip() in ("-", "") else int(_parse_greek_number(winners_raw))
        is_annuity = any(word in prize_raw for word in ("μήνα", "χρόνο", "χρόνια"))
        prize_number_match = None if is_annuity else re.match(r"[\d.,]+", prize_raw.strip())
        prize_amount = _parse_greek_number(prize_number_match.group()) if prize_number_match else None
        jackpot_amount = _parse_greek_number(distributed_raw) if distributed_raw.strip() else None

        if prize_amount is not None:
            total_payout_eur += winners * prize_amount

        tier_index += 1
        prize_tiers.append({
            "tier_class": tier_index,
            "description": f"{category} ({prize_raw.strip()})" if prize_amount is None else category,
            "winners_count": winners,
            "prize_amount": prize_amount,
            "jackpot_amount": jackpot_amount,
        })

    if not prize_tiers:
        raise AllwynScrapeError(f"Unexpected page shape for {game}; couldn't find the prize-tier table")

    return {
        "game": game,
        "draw_date": draw_date,
        "stakes_eur": stakes_eur,
        "total_payout_eur": total_payout_eur,
        "profit_eur": stakes_eur - total_payout_eur,
        "winning_numbers": {"draw_number": draw_number, "numbers": winning_numbers},
        "source": "playwright",
        "prize_tiers": prize_tiers,
    }
