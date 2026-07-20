"""Load data/manual/opap_quarterly_ggr.csv (the trustworthy ground-truth
figures, hand-verified against real OPAP press releases) into the DB.

Run this after editing the CSV, before forecasting/backtest.py.
"""
import csv
from pathlib import Path

from db.repository import connect, init_db, upsert_ggr

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "manual" / "opap_quarterly_ggr.csv"


def main() -> None:
    init_db()
    with connect() as conn, open(CSV_PATH, newline="", encoding="utf-8") as f:
        count = 0
        for row in csv.DictReader(f):
            upsert_ggr(
                conn,
                reporting_period=row["reporting_period"],
                segment=row["segment"],
                ggr_eur=float(row["ggr_eur"]),
                source_url=row["source_url"] or None,
                entry_method="manual",
                reported_date=row["reported_date"] or None,
            )
            count += 1
        print(f"Loaded {count} manual ground-truth rows from {CSV_PATH}")


if __name__ == "__main__":
    main()
