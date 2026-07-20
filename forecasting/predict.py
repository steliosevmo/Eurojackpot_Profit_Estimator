"""Predict GGR for the next reporting period that doesn't have an actual figure yet."""
import pickle

from db.repository import connect, upsert_prediction
from forecasting.dataset import FEATURE_NAMES, TARGET_SEGMENT, denormalize_rate, period_sort_key
from forecasting.train_model import MODEL_PATH


def _next_unreported_period(target_segment: str) -> str | None:
    with connect() as conn:
        known_periods = {r["reporting_period"] for r in conn.execute(
            "SELECT reporting_period FROM opap_quarterly_ggr WHERE segment = ?", (target_segment,)
        )}
        feature_periods = {r["reporting_period"] for r in conn.execute(
            "SELECT DISTINCT reporting_period FROM quarterly_features"
        )}
    candidates = sorted(feature_periods - known_periods, key=period_sort_key)
    return candidates[-1] if candidates else None


def predict_next(target_segment: str = TARGET_SEGMENT) -> dict | None:
    if not MODEL_PATH.exists():
        raise RuntimeError("No trained model found; run forecasting/train_model.py first")

    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)

    period = _next_unreported_period(target_segment)
    if period is None:
        print("No reporting period with features but no actual GGR yet -- nothing to predict")
        return None

    with connect() as conn:
        features = {r["feature_name"]: r["feature_value"] for r in conn.execute(
            "SELECT feature_name, feature_value FROM quarterly_features WHERE reporting_period = ?", (period,)
        )}
        days = features.get("period_length_days") or 1
        row = [[(features.get(name, 0.0) or 0.0) / days for name in FEATURE_NAMES]]
        predicted_rate = float(bundle["model"].predict(row)[0])
        predicted_ggr = denormalize_rate(predicted_rate, days)

        upsert_prediction(
            conn,
            reporting_period=period,
            target_segment=target_segment,
            predicted_ggr=predicted_ggr,
            actual_ggr=None,
            mape=None,
            model_version=bundle["version"],
        )

    print(f"Predicted {target_segment} GGR for {period}: EUR {predicted_ggr:,.0f}")
    return {"reporting_period": period, "target_segment": target_segment, "predicted_ggr": predicted_ggr}


if __name__ == "__main__":
    predict_next()
