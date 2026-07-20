"""Best-effort scraper for OPAP's investor relations press releases (investors.opap.gr).

This is deliberately conservative: financial PDFs vary in layout release to
release, so instead of trying to be clever, this looks for a small set of
known segment labels followed by a euro figure, and returns nothing for a
segment it isn't confident about rather than guessing. It is NOT the
source of truth used for backtesting -- data/manual/opap_quarterly_ggr.csv
(entry_method='manual', filled in by hand from the actual press release) is.
Anything this scraper finds is stored with entry_method='scraped' and should
be treated as a convenience cross-check, not ground truth.

investors.opap.gr also shows a cookie-consent banner that blocks the page
content until dismissed, so this needs Playwright rather than a plain HTTP
GET (which 403s/renders an empty shell for the same reason allwyn.gr does).
"""
import io
import re

import pdfplumber
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "https://investors.opap.gr"

SEGMENT_LABELS = {
    "numerical_lotteries": [r"numerical\s+lotter(?:y|ies)", r"lotter(?:y|ies)"],
    "sports_betting": [r"sports?\s+betting", r"betting"],
    "vlts": [r"vlts?", r"video\s+lottery"],
    "online": [r"online", r"igaming"],
    "total": [r"\btotal\s+ggr\b", r"gross\s+gaming\s+revenue"],
}
MONEY_PATTERN = re.compile(r"€?\s?([\d,]+\.\d)\s?(?:m|million)?", re.IGNORECASE)


class OpapIrScrapeError(Exception):
    """Raised when the IR site itself can't be reached/parsed (not when a segment is simply not found)."""


def list_report_pdfs(year: int) -> list[str]:
    """Best-effort: return PDF links found on the financial-statements/<year> page."""
    url = f"{BASE_URL}/en/results-and-news/financial-statements/{year}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            for button_text in ("Reject", "Reject All", "Necessary only"):
                locator = page.get_by_text(button_text, exact=False)
                if locator.count() > 0:
                    try:
                        locator.first.click(timeout=3_000)
                        break
                    except Exception:
                        pass
            hrefs = page.eval_on_selector_all("a[href$='.pdf']", "els => els.map(e => e.href)")
        except Exception as exc:
            raise OpapIrScrapeError(str(exc)) from exc
        finally:
            browser.close()
    return sorted(set(hrefs))


def extract_segment_ggr(pdf_url: str) -> dict:
    """Best-effort: {segment: euro_amount} for whatever segments were confidently found."""
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OpapIrScrapeError(f"Could not download {pdf_url}: {exc}") from exc

    text = ""
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"

    found = {}
    for segment, patterns in SEGMENT_LABELS.items():
        for pattern in patterns:
            match = re.search(pattern + r".{0,40}?" + MONEY_PATTERN.pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                amount_str = match.group(1).replace(",", "")
                found[segment] = float(amount_str) * 1_000_000  # figures are reported in EUR millions
                break
    return found


if __name__ == "__main__":
    import sys
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    for pdf_url in list_report_pdfs(year):
        print(pdf_url)
        try:
            print(extract_segment_ggr(pdf_url))
        except OpapIrScrapeError as exc:
            print(f"  skipped: {exc}")
