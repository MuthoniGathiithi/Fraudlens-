"""
Fraud detection layer: combines an unsupervised ML model (Isolation Forest)
with explainable business rules — the same hybrid approach real fintech fraud
systems use, because a pure black-box model is hard to justify to reviewers,
and pure rules miss novel patterns.
"""
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURE_COLUMNS = ["amount", "hour_of_day", "is_new_device", "is_unknown_location"]


class FraudDetector:
    def __init__(self):
        self.model = IsolationForest(
            n_estimators=150,
            contamination=0.08,   # expected % of anomalies — tune against real data later
            random_state=42,
        )
        self.is_fitted = False
        # calibration bounds learned from training data, used to normalize
        # decision_function output into a stable 0-1 risk score
        self._df_min = 0.0
        self._df_max = 0.0
        # tracks recent transaction timestamps per sender for velocity rule
        self._recent_by_sender: dict[str, list[datetime]] = defaultdict(list)

    # ---- feature engineering ----
    def _featurize(self, rows: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(rows)
        df["is_new_device"] = df["device_id"].astype(str).str.startswith("NEW_DEVICE").astype(int)
        df["is_unknown_location"] = (df["location"] == "Unknown").astype(int)
        return df

    # ---- training ----
    def fit(self, historical_rows: list[dict]):
        df = self._featurize(historical_rows)
        self.model.fit(df[FEATURE_COLUMNS])

        # calibrate: record the range of decision_function scores on the
        # training set itself, so risk scores are relative to *this* data's
        # normal/abnormal spread rather than an assumed fixed range
        train_scores = self.model.decision_function(df[FEATURE_COLUMNS])
        self._df_min = float(np.percentile(train_scores, 1))   # ~most anomalous
        self._df_max = float(np.percentile(train_scores, 99))  # ~most normal
        self.is_fitted = True

    # ---- velocity rule: N+ transactions from same sender within a short window ----
    def _velocity_flag(self, sender_id: str, ts: datetime, window_seconds: int = 60, threshold: int = 3) -> bool:
        history = self._recent_by_sender[sender_id]
        history.append(ts)
        cutoff = ts - timedelta(seconds=window_seconds)
        history[:] = [t for t in history if t >= cutoff]
        return len(history) >= threshold

    # ---- scoring a single transaction ----
    def score(self, row: dict) -> dict:
        reasons = []

        df = self._featurize([row])
        if self.is_fitted:
            # decision_function: higher = more normal. We flip + normalize to a 0-1 risk score.
            raw = self.model.decision_function(df[FEATURE_COLUMNS])[0]
            ml_risk = float(np.clip((0.5 - raw) * 2, 0, 1))  # rough normalization
            is_ml_outlier = self.model.predict(df[FEATURE_COLUMNS])[0] == -1
        else:
            ml_risk, is_ml_outlier = 0.0, False

        if is_ml_outlier:
            reasons.append("statistical outlier (ML model)")

        # explainable rules layered on top
        if row["amount"] >= 2000:
            reasons.append("unusually large amount")
        if row["hour_of_day"] in (2, 3, 4):
            reasons.append("transaction at unusual hour")
        if str(row["device_id"]).startswith("NEW_DEVICE"):
            reasons.append("new/unrecognized device")
        if row["location"] == "Unknown":
            reasons.append("unknown location")
        if self._velocity_flag(row["sender_id"], row["timestamp"]):
            reasons.append("rapid succession of transactions (velocity)")

        rule_risk = min(len(reasons) * 0.2, 1.0)
        final_risk = max(ml_risk, rule_risk)
        is_flagged = final_risk >= 0.4 or len(reasons) >= 2

        return {
            "risk_score": round(final_risk, 3),
            "is_flagged": is_flagged,
            "flag_reasons": ", ".join(reasons) if reasons else "",
        }


# module-level singleton so state (velocity tracking, fitted model) persists across requests
detector = FraudDetector()