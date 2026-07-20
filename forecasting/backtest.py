"""Walk-forward backtest: for each reporting period with a known actual GGR,
train only on strictly earlier periods, predict, then compare to what OPAP
actually reported. This is the "test our prediction against the real report"
loop the user asked for.

Needs at least 2 periods with actual GGR (1 to train on, 1 to test) to
produce any result at all; more periods give a more meaningful score.
"""
import csv
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge

from db.repository import connect, upsert_prediction
from forecasting.dataset import TARGET_SEGMENT, denormalize_rate, load_period_rows, to_matrix
from forecasting.train_model import MODEL_VERSION

REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "backtest_report.csv"


def run_backtest(target_segment: str = TARGET_SEGMENT) -> list[dict]:
    dataset = load_period_rows(target_segment)
    if len(dataset) < 2:
        print(f"Only {len(dataset)} period(s) available -- need at least 2 to backtest. "
              "Add more rows to data/manual/opap_quarterly_ggr.csv as more OPAP reports come out.")
        return []

    results = []
    with connect() as conn:
        for i in range(1, len(dataset)):
            train_rows = dataset[:i]
            test_row = dataset[i]

            X_train, y_train = to_matrix(train_rows)
            model = Ridge(alpha=1.0)
            model.fit(np.array(X_train), np.array(y_train))

            X_test, _ = to_matrix([test_row])
            predicted_rate = float(model.predict(np.array(X_test))[0])
            predicted = denormalize_rate(predicted_rate, test_row["period_length_days"])
            actual = test_row["actual_ggr"]

            abs_error = abs(predicted - actual)
            mape = abs_error / actual if actual else None

            prior_actual = train_rows[-1]["actual_ggr"]
            actual_direction = actual > prior_actual
            predicted_direction = predicted > prior_actual
            direction_correct = actual_direction == predicted_direction

            upsert_prediction(
                conn,
                reporting_period=test_row["reporting_period"],
                target_segment=target_segment,
                predicted_ggr=predicted,
                actual_ggr=actual,
                mape=mape,
                model_version=f"{MODEL_VERSION}-backtest",
            )

            results.append({
                "reporting_period": test_row["reporting_period"],
                "predicted_ggr": predicted,
                "actual_ggr": actual,
                "abs_error": abs_error,
                "mape": mape,
                "direction_correct": direction_correct,
            })

    _write_report(results)
    _print_summary(results)
    return results


def _write_report(results: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["reporting_period", "predicted_ggr", "actual_ggr",
                                                "abs_error", "mape", "direction_correct"])
        writer.writeheader()
        writer.writerows(results)


def _print_summary(results: list[dict]) -> None:
    mapes = [r["mape"] for r in results if r["mape"] is not None]
    hit_rate = sum(r["direction_correct"] for r in results) / len(results)
    print(f"Backtested {len(results)} period(s):")
    for r in results:
        print(f"  {r['reporting_period']}: predicted={r['predicted_ggr']:,.0f} "
              f"actual={r['actual_ggr']:,.0f} MAPE={r['mape']:.1%} "
              f"direction={'correct' if r['direction_correct'] else 'wrong'}")
    if mapes:
        print(f"Mean MAPE: {sum(mapes) / len(mapes):.1%}  |  Directional hit rate: {hit_rate:.0%}")
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    run_backtest()
