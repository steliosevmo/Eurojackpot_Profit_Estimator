"""Build the (features, actual_ggr) table shared by train_model.py and backtest.py."""
import re

from db.repository import connect

TARGET_SEGMENT = "numerical_lotteries"  # the only OPAP segment our scrapers can plausibly explain

# End-month of each period label, so periods sort by when they actually end
# rather than alphabetically ("2025-FY" would otherwise sort before "2025-Q1").
_PERIOD_END_MONTH = {"Q1": 3, "Q2": 6, "H1": 6, "Q3": 9, "9M": 9, "Q4": 12, "FY": 12}
# Cumulative periods (H1/9M/FY) cover more ground than a single quarter ending
# the same month, so they sort after it.
_PERIOD_IS_CUMULATIVE = {"H1", "9M", "FY"}


def period_sort_key(period: str) -> tuple[int, int, bool]:
    match = re.match(r"(\d{4})-(Q1|Q2|Q3|Q4|H1|9M|FY)$", period)
    if not match:
        raise ValueError(f"Unrecognized reporting_period label: {period!r}")
    year, label = match.groups()
    return (int(year), _PERIOD_END_MONTH[label], label in _PERIOD_IS_CUMULATIVE)


def load_period_rows(target_segment: str = TARGET_SEGMENT) -> list[dict]:
    """One row per reporting_period that has both features and a known actual GGR."""
    with connect() as conn:
        ggr_rows = conn.execute(
            "SELECT reporting_period, ggr_eur FROM opap_quarterly_ggr WHERE segment = ?",
            (target_segment,),
        ).fetchall()
        feature_rows = conn.execute(
            "SELECT reporting_period, feature_name, feature_value FROM quarterly_features"
        ).fetchall()

    features_by_period: dict[str, dict] = {}
    for row in feature_rows:
        features_by_period.setdefault(row["reporting_period"], {})[row["feature_name"]] = row["feature_value"]

    dataset = []
    for row in ggr_rows:
        period = row["reporting_period"]
        features = features_by_period.get(period)
        if not features:
            continue  # we have no scraped draws covering this period -- can't build features for it
        dataset.append({"reporting_period": period, "actual_ggr": row["ggr_eur"], **features})

    dataset.sort(key=lambda r: period_sort_key(r["reporting_period"]))
    return dataset


FEATURE_NAMES = [
    "eurojackpot_stakes_sum", "eurojackpot_payout_sum", "eurojackpot_draw_count",
    "joker_stakes_sum", "joker_payout_sum", "joker_draw_count",
    "lotto_stakes_sum", "lotto_payout_sum", "lotto_draw_count",
    "combined_stakes_sum",
]


def to_matrix(dataset: list[dict]) -> tuple[list[list[float]], list[float]]:
    """Per-day rates, not raw period sums.

    A quarter's summed stakes are naturally ~1/4 of a full year's, so
    training directly on raw sums would make the model think GGR itself
    scales with how long the period is rather than genuine growth. Dividing
    every sum/count feature (and the actual_ggr target) by the period's
    calendar length puts a "2025-Q1" row and a "2025-FY" row on the same
    footing. `denormalize_rate` converts a predicted rate back to an
    absolute figure for a given period.
    """
    X, y = [], []
    for row in dataset:
        days = row.get("period_length_days") or 1
        X.append([(row.get(name, 0.0) or 0.0) / days for name in FEATURE_NAMES])
        y.append(row["actual_ggr"] / days)
    return X, y


def denormalize_rate(rate: float, period_length_days: float) -> float:
    return rate * period_length_days
