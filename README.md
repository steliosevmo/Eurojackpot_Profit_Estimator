# Eurojackpot / OPAP GGR Forecasting Platform

What started as a single Selenium script scraping Eurojackpot's site has grown into a small pipeline:
scrape Eurojackpot, Joker and Lotto draw data into a SQLite database on a schedule, then use it to
forecast **OPAP SA's** quarterly Gross Gaming Revenue (GGR) and backtest each forecast against what
OPAP actually reports.

This is still an educational/hobby project (see the original disclaimer below) — the forecasting
model is a simple regression trained on very few data points, not investment advice.

## Architecture

```
scrapers/
  eurojackpot_api.py        # primary: reverse-engineered JSON API (eurojackpot.com/wlinfo)
  eurojackpot_playwright.py # fallback if the API call fails
  joker_scraper.py           # Playwright scrape of allwyn.gr (no public API; site blocks plain HTTP)
  lotto_scraper.py           # same, for Lotto
  _allwyn_common.py          # shared Joker/Lotto page-parsing logic
  opap_ir_scraper.py         # best-effort scrape of OPAP investor-relations press releases

db/
  schema.sql                 # SQLite schema
  repository.py               # sqlite3 data-access layer

pipeline/
  scrape_latest.py            # run by .github/workflows/scrape.yml on a schedule
  backfill_history.py          # one-off: backfill Eurojackpot draws back to 2012
  build_quarterly_features.py  # aggregate draws into per-reporting-period features
  load_manual_ggr.py            # load data/manual/opap_quarterly_ggr.csv into the DB

forecasting/
  dataset.py         # joins features to actual GGR
  train_model.py      # Ridge/GradientBoosting regression, cross-validated
  predict.py           # forecast the next not-yet-reported period
  backtest.py           # walk-forward backtest against actual reported GGR

data/
  lottery.db                       # SQLite DB, committed to the repo
  manual/opap_quarterly_ggr.csv     # ground-truth OPAP GGR figures (see below)
```

## Data sources and their limitations

- **Eurojackpot**: `eurojackpot.com` has a real JSON API behind its Angular frontend
  (`wlinfo/WL_InfoService`) that returns stakes, the full prize-tier breakdown, and winning numbers
  for any date, plus a list of every draw date back to 2012. This is the primary scraper; Playwright
  is only a fallback if that endpoint ever changes shape.
- **Joker / Lotto**: OPAP's retail site (now under parent company Allwyn, `allwyn.gr`) returns 403 to
  plain HTTP clients — there's no usable API, so these use Playwright. Their results pages do publish
  "Σύνολο Στηλών" (total columns played), which at €1/column is a genuine stakes figure, plus a full
  prize-tier table — so unlike an initial assumption, these aren't just payout proxies. One real gap:
  only the *current* draw is scraped; historical Joker/Lotto backfill would require driving the site's
  year/month/draw-number search form, which isn't implemented yet.
- **OPAP's actual reported GGR** (the "official data" forecasts are graded against) comes from
  `investors.opap.gr`. Financial PDFs vary in layout release to release, so `opap_ir_scraper.py` is
  best-effort and only fills in a segment when it's confident — it is **not** the source of truth.
  `data/manual/opap_quarterly_ggr.csv` is: it's hand-populated from real OPAP press releases (each row
  cites its source URL) and is what `forecasting/backtest.py` actually grades against. Add a row there
  whenever a new OPAP report comes out.

## Forecasting & backtesting

The model predicts OPAP's `numerical_lotteries` segment GGR (the only segment our scrapers can
plausibly explain) from that period's aggregated Eurojackpot/Joker/Lotto stakes and payouts.
`forecasting/backtest.py` walks forward through history: for each reporting period with a known
actual GGR, it trains only on strictly earlier periods, predicts, and compares — writing
`data/backtest_report.csv` with per-period error (MAPE) and whether it called growth vs. decline
correctly. This needs at least 2 populated periods in the manual CSV to produce anything, and gets
more meaningful as more real reports are added over time.

## Running things locally

```
pip install -r requirements.txt
playwright install chromium

python -m pipeline.scrape_latest              # scrape today's draws into data/lottery.db
python -m pipeline.backfill_history            # one-off: backfill Eurojackpot since 2012
python -m pipeline.load_manual_ggr             # load the ground-truth CSV
python -m pipeline.build_quarterly_features    # aggregate draws into features
python -m forecasting.train_model              # train the regression model
python -m forecasting.backtest                 # walk-forward backtest -> data/backtest_report.csv
python -m forecasting.predict                  # forecast the next unreported period
```

## CI/CD

- `.github/workflows/scrape.yml` runs `pipeline.scrape_latest` daily and commits the updated DB back
  to the repo.
- `.github/workflows/backtest.yml` runs roughly quarterly (and on demand via
  `workflow_dispatch`): loads the manual ground-truth CSV, builds features, retrains, backtests, and
  predicts the next period, committing the results.

## Original disclaimer

This still doesn't calculate exact real-world profit for any of these games or companies — taxes,
marketing, and other operating costs aren't in scope, and the GGR forecast is a small-data regression,
not investment advice. The project exists to build real scraping/data-pipeline/ML skills, motivated by
an interest in gambling-sector stocks (OPAP SA, Flutter Entertainment).
