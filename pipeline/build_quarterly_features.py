"""Aggregate draw-level rows into per-reporting-period features.

Each draw is bucketed into both its calendar quarter ("2025-Q1") and its
calendar year ("2025-FY"), since OPAP's own disclosures mix quarterly and
cumulative (FY/H1/9M) periods -- forecasting/train_model.py joins whichever
of these match a period present in opap_quarterly_ggr. A quarter and a full
year obviously aren't the same scale, so `period_length_days` is stored
alongside the raw sums -- dataset.py uses it to turn sums into per-day rates
that are actually comparable across period types.
"""
from collections import defaultdict
from datetime import date, timedelta

from db.repository import connect, init_db, upsert_feature

GAMES = ("eurojackpot", "joker", "lotto")


def _periods_for(draw_date: str) -> list[str]:
    d = date.fromisoformat(draw_date)
    quarter = (d.month - 1) // 3 + 1
    return [f"{d.year}-Q{quarter}", f"{d.year}-FY"]


def _period_length_days(period: str) -> int:
    year_str, label = period.split("-")
    year = int(year_str)
    if label == "FY":
        start, end = date(year, 1, 1), date(year, 12, 31)
    else:
        quarter = int(label[1])
        start = date(year, (quarter - 1) * 3 + 1, 1)
        next_quarter_start = (
            date(year + 1, 1, 1) if quarter == 4 else date(year, quarter * 3 + 1, 1)
        )
        end = next_quarter_start - timedelta(days=1)
    return (end - start).days + 1


def main() -> None:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT game, draw_date, stakes_eur, total_payout_eur FROM draws"
        ).fetchall()

        totals = defaultdict(lambda: {"stakes_sum": 0.0, "payout_sum": 0.0, "draw_count": 0})
        for row in rows:
            if row["stakes_eur"] is None:
                continue
            for period in _periods_for(row["draw_date"]):
                bucket = totals[(period, row["game"])]
                bucket["stakes_sum"] += row["stakes_eur"]
                bucket["payout_sum"] += row["total_payout_eur"] or 0.0
                bucket["draw_count"] += 1

        combined_stakes = defaultdict(float)
        for (period, game), agg in totals.items():
            for metric, value in agg.items():
                upsert_feature(conn, reporting_period=period, feature_name=f"{game}_{metric}", feature_value=value)
            combined_stakes[period] += agg["stakes_sum"]

        for period, value in combined_stakes.items():
            upsert_feature(conn, reporting_period=period, feature_name="combined_stakes_sum", feature_value=value)
            upsert_feature(conn, reporting_period=period, feature_name="period_length_days",
                           feature_value=_period_length_days(period))

        print(f"Built features for {len(combined_stakes)} reporting periods across {len(GAMES)} games")


if __name__ == "__main__":
    main()
