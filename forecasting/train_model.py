"""Train a small regression model to predict OPAP's numerical-lotteries GGR
for a reporting period from that period's scraped draw-level features.

OPAP has realistically a few dozen periods of consistent segment reporting
at most, so this deliberately favors simple, regularized models
(cross-validated between Ridge and GradientBoosting) over anything that
needs a lot of training data.
"""
import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_score

from forecasting.dataset import load_period_rows, to_matrix

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "ggr_model.pkl"
MODEL_VERSION = "v1"

CANDIDATES = {
    "ridge": Ridge(alpha=1.0),
    "gradient_boosting": GradientBoostingRegressor(n_estimators=50, max_depth=2, random_state=0),
}


def train(min_periods_for_cv: int = 5):
    dataset = load_period_rows()
    if len(dataset) < 2:
        raise RuntimeError(
            f"Only {len(dataset)} reporting period(s) have both features and ground truth -- "
            "need at least 2 to fit a model. Run pipeline/scrape_latest.py for a while longer, "
            "or add more rows to data/manual/opap_quarterly_ggr.csv."
        )

    X, y = to_matrix(dataset)
    X, y = np.array(X), np.array(y)

    best_name, best_model, best_score = None, None, -np.inf
    n_splits = min(len(dataset), min_periods_for_cv)
    for name, model in CANDIDATES.items():
        if len(dataset) >= 3:
            scores = cross_val_score(model, X, y, cv=KFold(n_splits=min(n_splits, len(dataset))),
                                      scoring="neg_mean_absolute_percentage_error")
            score = scores.mean()
        else:
            score = 0.0  # not enough data to cross-validate; just pick Ridge as the safe default
            if name != "ridge":
                continue
        if score > best_score:
            best_name, best_model, best_score = name, model, score

    best_model.fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": best_model, "model_name": best_name, "version": MODEL_VERSION}, f)

    print(f"Trained {best_name} on {len(dataset)} periods (cv MAPE score={-best_score:.4f}); saved to {MODEL_PATH}")
    return best_model, best_name


if __name__ == "__main__":
    train()
