"""VISHWAS Phase 2 Real-Data Validation: Real-Data ML Training and Split Conformal Prediction Calibration.

Step 5:
- Load: backend/data/real/features/august_2023_matrix.parquet
- Features (7 synoptic & spatial features):
    ['f_apcp_24h', 'f_cape', 'f_hgt_500', 'f_u_850', 'f_v_850', 'lat', 'lon']
- Target: error_abs
- Chronological Split:
    Training:    August 1–21 (valid Aug 2–21, 98,100 samples)
    Calibration: August 22–26 (valid Aug 22–26, 24,525 samples)
    Test:        August 27–31 (valid Aug 27–31, 24,525 samples)
  Strict assertion: max(train) < min(calib) < min(test)
- Baselines:
    Median-error baseline on test set
- XGBoost:
    XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42, tree_method="hist")
    Fitted strictly on Training set only.
- MAPIE Split Conformal Regressor (Split Conformal Prediction):
    confidence_level=0.80 (nominal 80% coverage)
    Conformalized strictly on Calibration set only.
- Evaluation on Test Set:
    Baseline MAE, RMSE vs XGBoost MAE, RMSE
    Empirical test coverage, mean & median interval width
    Test sample count, bust count, bust prevalence
- Artifacts:
    backend/data/real/models/cqr_model.pkl (legacy compatibility filename for split conformal calibrator)
    backend/data/real/models/cqr_metrics.json (legacy compatibility filename for evaluation metrics)
"""

import os
import sys
import pickle
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from mapie.regression import SplitConformalRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURE_COLS = [
    "f_apcp_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "lat",
    "lon"
]

TARGET_COL = "error_abs"

def train_and_calibrate(
    matrix_path: str = "backend/data/real/features/august_2023_matrix.parquet",
    model_output_path: str = "backend/data/real/models/cqr_model.pkl",
    metrics_output_path: str = "backend/data/real/models/cqr_metrics.json"
) -> dict:
    """Train XGBoost model and calibrate conformal prediction intervals chronologically."""
    print(f"[ML] Loading historical feature matrix: {matrix_path}")
    df = pd.read_parquet(matrix_path)
    df["valid_time"] = pd.to_datetime(df["valid_time"])

    # Chronological Split
    train_df = df[df["valid_time"] <= pd.Timestamp("2023-08-21")].copy()
    calib_df = df[(df["valid_time"] >= pd.Timestamp("2023-08-22")) & (df["valid_time"] <= pd.Timestamp("2023-08-26"))].copy()
    test_df = df[df["valid_time"] >= pd.Timestamp("2023-08-27")].copy()

    # Explicit chronological assertions
    max_train = train_df["valid_time"].max()
    min_calib = calib_df["valid_time"].min()
    max_calib = calib_df["valid_time"].max()
    min_test = test_df["valid_time"].min()

    print(f"[ML] Chronological Split:")
    print(f"     Train: {len(train_df):,} samples ({train_df['valid_time'].min().strftime('%Y-%m-%d')} to {max_train.strftime('%Y-%m-%d')})")
    print(f"     Calib: {len(calib_df):,} samples ({min_calib.strftime('%Y-%m-%d')} to {max_calib.strftime('%Y-%m-%d')})")
    print(f"     Test:  {len(test_df):,} samples ({min_test.strftime('%Y-%m-%d')} to {test_df['valid_time'].max().strftime('%Y-%m-%d')})")

    assert max_train < min_calib, f"Train-Calib order violation: max(train)={max_train} >= min(calib)={min_calib}"
    assert max_calib < min_test, f"Calib-Test order violation: max(calib)={max_calib} >= min(test)={min_test}"
    print("[ML] Chronological split assertions strictly satisfied.")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL].values
    X_calib, y_calib = calib_df[FEATURE_COLS], calib_df[TARGET_COL].values
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL].values

    # 1. Baseline: median-error baseline computed strictly from training target
    baseline_median = float(np.median(y_train))
    baseline_pred = np.full(len(y_test), baseline_median)
    base_mae = float(mean_absolute_error(y_test, baseline_pred))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_pred)))

    # 2. XGBoost Base Estimator
    print("[ML] Training XGBoost Regressor on Training set only...")
    base_model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        tree_method="hist"
    )
    base_model.fit(X_train, y_train)

    xgb_pred = base_model.predict(X_test)
    xgb_mae = float(mean_absolute_error(y_test, xgb_pred))
    xgb_rmse = float(np.sqrt(mean_squared_error(y_test, xgb_pred)) )

    # 3. MAPIE Conformal Calibration (Split Conformal Prediction)
    print("[ML] Conformalizing MAPIE SplitConformalRegressor on Calibration set only...")
    nominal_coverage = 0.80
    conformal_reg = SplitConformalRegressor(
        estimator=base_model,
        confidence_level=nominal_coverage,
        prefit=True
    )
    conformal_reg.conformalize(X_calib, y_calib)

    # 4. Evaluation on Test Set
    pred_cqr, intervals = conformal_reg.predict_interval(X_test)
    lower = np.maximum(intervals[:, 0, 0], 0.0)
    upper = intervals[:, 1, 0]

    covered = (y_test >= lower) & (y_test <= upper)
    empirical_coverage = float(np.mean(covered) * 100.0)
    widths = upper - lower
    mean_width = float(np.mean(widths))
    median_width = float(np.median(widths))

    num_test = len(test_df)
    bust_count = int(test_df["is_bust"].sum())
    bust_prevalence = float(test_df["is_bust"].mean() * 100.0)

    metrics = {
        "dataset": {
            "total_samples": len(df),
            "train_samples": len(train_df),
            "calib_samples": len(calib_df),
            "test_samples": num_test,
            "test_bust_count": bust_count,
            "test_bust_prevalence_pct": round(bust_prevalence, 2)
        },
        "baseline": {
            "name": "Median Error Baseline (Train Set)",
            "median_error": round(baseline_median, 4),
            "mae": round(base_mae, 4),
            "rmse": round(base_rmse, 4)
        },
        "xgboost": {
            "mae": round(xgb_mae, 4),
            "rmse": round(xgb_rmse, 4),
            "mae_improvement_pct": round(((base_mae - xgb_mae) / base_mae) * 100.0, 2),
            "rmse_improvement_pct": round(((base_rmse - xgb_rmse) / base_rmse) * 100.0, 2)
        },
        "cqr_conformal": {
            "nominal_coverage_pct": 80.0,
            "empirical_coverage_pct": round(empirical_coverage, 2),
            "mean_interval_width": round(mean_width, 4),
            "median_interval_width": round(median_width, 4),
            "theoretical_assumptions": "Conformal coverage guarantees assume exchangeability of nonconformity scores between calibration and test sets under split conformal regression. Weather time series exhibit temporal autocorrelation and synoptic regime transitions that may modulate finite-sample conditional coverage."
        }
    }

    print("\n" + "=" * 60)
    print("REAL-DATA ML & CONFORMAL CALIBRATION RESULTS")
    print("=" * 60)
    print(f"Test Samples:       {num_test:,} (Busts: {bust_count:,}, {bust_prevalence:.2f}%)")
    print(f"Baseline MAE:       {base_mae:.4f} mm | RMSE: {base_rmse:.4f} mm")
    print(f"XGBoost MAE:        {xgb_mae:.4f} mm | RMSE: {xgb_rmse:.4f} mm ({metrics['xgboost']['mae_improvement_pct']}% MAE improvement)")
    print(f"Nominal Coverage:   80.00%")
    print(f"Empirical Coverage: {empirical_coverage:.2f}%")
    print(f"Mean Width:         {mean_width:.4f} mm | Median Width: {median_width:.4f} mm")
    print("=" * 60 + "\n")

    # Save Model Artifact
    out_model_p = Path(model_output_path)
    out_model_p.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "xgboost_model": base_model,
        "conformal_regressor": conformal_reg,
        "feature_cols": FEATURE_COLS,
        "target_col": TARGET_COL,
        "metrics": metrics,
        "train_max_valid_time": str(max_train),
        "calib_range": (str(min_calib), str(max_calib)),
        "test_range": (str(min_test), str(test_df["valid_time"].max()))
    }

    with open(out_model_p, "wb") as f:
        pickle.dump(artifact, f)
    print(f"[ML] Model artifact saved to: {out_model_p}")

    out_metrics_p = Path(metrics_output_path)
    out_metrics_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_metrics_p, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[ML] Metrics summary saved to: {out_metrics_p}")

    return metrics


def verify_trained_model(
    model_path: str = "backend/data/real/models/cqr_model.pkl",
    metrics_path: str = "backend/data/real/models/cqr_metrics.json"
) -> bool:
    """Verify saved model artifact can be reloaded and yields expected inference."""
    mp = Path(model_path)
    jp = Path(metrics_path)
    if not mp.exists() or not jp.exists():
        print(f"[VERIFY FAILED] Model or metrics file missing: {mp}, {jp}")
        return False

    try:
        with open(mp, "rb") as f:
            artifact = pickle.load(f)

        assert "xgboost_model" in artifact, "Missing 'xgboost_model'"
        assert "conformal_regressor" in artifact, "Missing 'conformal_regressor'"
        assert "feature_cols" in artifact, "Missing 'feature_cols'"

        # Test inference with synthetic dummy sample
        dummy_X = pd.DataFrame([{
            "f_apcp_24h": 15.0,
            "f_cape": 800.0,
            "f_hgt_500": 5850.0,
            "f_u_850": 5.0,
            "f_v_850": -3.0,
            "lat": 20.0,
            "lon": 85.0
        }])

        pred = artifact["xgboost_model"].predict(dummy_X)
        assert len(pred) == 1, "Inference prediction failed"

        _, intervals = artifact["conformal_regressor"].predict_interval(dummy_X)
        assert intervals.shape == (1, 2, 1), f"Unexpected interval shape: {intervals.shape}"

        with open(jp, "r") as f:
            metrics = json.load(f)

        assert metrics["xgboost"]["mae"] < metrics["baseline"]["mae"], "XGBoost did not outperform baseline"
        assert 70.0 <= metrics["cqr_conformal"]["empirical_coverage_pct"] <= 95.0, "Empirical coverage unexpected"

        print(f"[VERIFY PASS] Trained model and conformal calibrator verified: XGBoost MAE={metrics['xgboost']['mae']}, Empirical Coverage={metrics['cqr_conformal']['empirical_coverage_pct']}%")
        return True
    except Exception as e:
        print(f"[VERIFY FAILED] Model verification exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Train real-data XGBoost and calibrate MAPIE conformal intervals")
    parser.add_argument("--matrix", default="backend/data/real/features/august_2023_matrix.parquet", help="Feature matrix parquet path")
    parser.add_argument("--output-model", default="backend/data/real/models/cqr_model.pkl", help="Output model pickle path")
    parser.add_argument("--output-metrics", default="backend/data/real/models/cqr_metrics.json", help="Output metrics json path")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()

    if args.verify:
        v = verify_trained_model(args.output_model, args.output_metrics)
        sys.exit(0 if v else 1)

    train_and_calibrate(
        matrix_path=args.matrix,
        model_output_path=args.output_model,
        metrics_output_path=args.output_metrics
    )
    v = verify_trained_model(args.output_model, args.output_metrics)
    sys.exit(0 if v else 1)

if __name__ == "__main__":
    main()
