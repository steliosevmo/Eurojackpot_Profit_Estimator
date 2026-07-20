"""Thin sqlite3 data-access layer shared by scrapers and pipeline scripts."""
import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "lottery.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


@contextmanager
def connect(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_draw(conn, *, game, draw_date, stakes_eur, total_payout_eur,
                 profit_eur, winning_numbers, source, prize_tiers=None):
    """Insert or replace a draw row (keyed on game+draw_date) and its prize tiers."""
    cur = conn.execute(
        """
        INSERT INTO draws (game, draw_date, stakes_eur, total_payout_eur, profit_eur,
                            winning_numbers, source, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game, draw_date) DO UPDATE SET
            stakes_eur=excluded.stakes_eur,
            total_payout_eur=excluded.total_payout_eur,
            profit_eur=excluded.profit_eur,
            winning_numbers=excluded.winning_numbers,
            source=excluded.source,
            scraped_at=excluded.scraped_at
        """,
        (game, draw_date, stakes_eur, total_payout_eur, profit_eur,
         json.dumps(winning_numbers), source, _now()),
    )
    draw_id = cur.lastrowid
    if draw_id == 0:
        # ON CONFLICT UPDATE doesn't return lastrowid on some sqlite builds; look it up.
        draw_id = conn.execute(
            "SELECT id FROM draws WHERE game=? AND draw_date=?", (game, draw_date)
        ).fetchone()["id"]

    if prize_tiers:
        for tier in prize_tiers:
            conn.execute(
                """
                INSERT INTO draw_prize_tiers (draw_id, tier_class, description,
                                               winners_count, prize_amount, jackpot_amount)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(draw_id, tier_class) DO UPDATE SET
                    description=excluded.description,
                    winners_count=excluded.winners_count,
                    prize_amount=excluded.prize_amount,
                    jackpot_amount=excluded.jackpot_amount
                """,
                (draw_id, tier["tier_class"], tier.get("description"),
                 tier["winners_count"], tier.get("prize_amount"), tier.get("jackpot_amount")),
            )
    return draw_id


def draw_exists(conn, *, game, draw_date) -> bool:
    row = conn.execute(
        "SELECT 1 FROM draws WHERE game=? AND draw_date=?", (game, draw_date)
    ).fetchone()
    return row is not None


def upsert_ggr(conn, *, reporting_period, segment, ggr_eur, source_url, entry_method, reported_date):
    conn.execute(
        """
        INSERT INTO opap_quarterly_ggr (reporting_period, segment, ggr_eur, source_url,
                                         entry_method, reported_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(reporting_period, segment) DO UPDATE SET
            ggr_eur=excluded.ggr_eur,
            source_url=excluded.source_url,
            entry_method=excluded.entry_method,
            reported_date=excluded.reported_date
        """,
        (reporting_period, segment, ggr_eur, source_url, entry_method, reported_date),
    )


def upsert_feature(conn, *, reporting_period, feature_name, feature_value):
    conn.execute(
        """
        INSERT INTO quarterly_features (reporting_period, feature_name, feature_value)
        VALUES (?, ?, ?)
        ON CONFLICT(reporting_period, feature_name) DO UPDATE SET
            feature_value=excluded.feature_value
        """,
        (reporting_period, feature_name, feature_value),
    )


def export_draws_csv(conn, csv_path: Path) -> None:
    """Write every draw row (readable, no prize-tier detail) to a CSV for humans to skim."""
    rows = conn.execute(
        """
        SELECT game, draw_date, stakes_eur, total_payout_eur, profit_eur, source, scraped_at
        FROM draws ORDER BY game, draw_date
        """
    ).fetchall()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Game", "Date", "Stakes (EUR)", "Total Paid (EUR)", "Profit (EUR)", "Source", "Scraped At"])
        for row in rows:
            writer.writerow([row["game"], row["draw_date"], row["stakes_eur"],
                              row["total_payout_eur"], row["profit_eur"], row["source"], row["scraped_at"]])


def upsert_prediction(conn, *, reporting_period, target_segment, predicted_ggr,
                       actual_ggr, mape, model_version):
    conn.execute(
        """
        INSERT INTO ggr_predictions (reporting_period, target_segment, predicted_ggr,
                                      actual_ggr, mape, model_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(reporting_period, target_segment, model_version) DO UPDATE SET
            predicted_ggr=excluded.predicted_ggr,
            actual_ggr=excluded.actual_ggr,
            mape=excluded.mape,
            created_at=excluded.created_at
        """,
        (reporting_period, target_segment, predicted_ggr, actual_ggr, mape,
         model_version, _now()),
    )
