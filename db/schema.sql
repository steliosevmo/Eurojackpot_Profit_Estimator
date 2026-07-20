-- Draw-level data for Eurojackpot, Joker, Lotto.
-- Eurojackpot rows have stakes_eur/profit_eur populated (public data).
-- Joker/Lotto rows only have total_payout_eur — OPAP does not publish
-- per-draw stakes/turnover for these games, so they act as payout-based
-- revenue proxies rather than true stakes-based GGR.
CREATE TABLE IF NOT EXISTS draws (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game            TEXT NOT NULL CHECK (game IN ('eurojackpot', 'joker', 'lotto')),
    draw_date       TEXT NOT NULL,
    stakes_eur      REAL,
    total_payout_eur REAL,
    profit_eur      REAL,
    winning_numbers TEXT,
    source          TEXT NOT NULL CHECK (source IN ('api', 'playwright')),
    scraped_at      TEXT NOT NULL,
    UNIQUE (game, draw_date)
);

CREATE TABLE IF NOT EXISTS draw_prize_tiers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_id        INTEGER NOT NULL REFERENCES draws(id) ON DELETE CASCADE,
    tier_class     INTEGER NOT NULL,
    description    TEXT,
    winners_count  INTEGER NOT NULL,
    prize_amount   REAL,
    jackpot_amount REAL,
    UNIQUE (draw_id, tier_class)
);

-- Ground truth for backtesting: OPAP's actual reported GGR per segment.
-- entry_method distinguishes numbers we scraped (best-effort, may be wrong)
-- from numbers the user manually verified against the real press release.
CREATE TABLE IF NOT EXISTS opap_quarterly_ggr (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reporting_period TEXT NOT NULL,
    segment         TEXT NOT NULL CHECK (segment IN
                        ('numerical_lotteries', 'sports_betting', 'vlts', 'online', 'total')),
    ggr_eur         REAL NOT NULL,
    source_url      TEXT,
    entry_method    TEXT NOT NULL CHECK (entry_method IN ('scraped', 'manual')),
    reported_date   TEXT,
    UNIQUE (reporting_period, segment)
);

-- Tidy/long-format feature store: one row per (period, feature) pair,
-- so new features can be added without a migration.
CREATE TABLE IF NOT EXISTS quarterly_features (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reporting_period TEXT NOT NULL,
    feature_name     TEXT NOT NULL,
    feature_value    REAL,
    UNIQUE (reporting_period, feature_name)
);

CREATE TABLE IF NOT EXISTS ggr_predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reporting_period TEXT NOT NULL,
    target_segment   TEXT NOT NULL,
    predicted_ggr    REAL NOT NULL,
    actual_ggr       REAL,
    mape             REAL,
    model_version    TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    UNIQUE (reporting_period, target_segment, model_version)
);
