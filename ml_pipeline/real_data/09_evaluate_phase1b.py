"""VISHWAS Phase 1B: Multi-Month Real-Data Validation and Cross-Month Evaluation Package.

Executes three standardized experiments across July, August, and September 2023:
- Experiment A: Month-by-month replication (July 2023, August 2023 Phase 1A baseline, September 2023)
- Experiment B: Pooled retrospective evaluation (3-month pooled model: 294,300 train, 73,575 calib, 73,575 test)
- Experiment C: Retrospective cross-month transfer (Leave-one-month-out: hold out July, hold out August, hold out September)

Outputs structured results to: ml_pipeline/real_data/phase1b_multimonth_metrics.json
"""

import os
import sys
import json
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from mapie.regression import SplitConformalRegressor
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    balanced_accuracy_score,
    matthews_corrcoef,
    mean_absolute_error,
    mean_squared_error,
)

# Set UTF-8 encoding on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

XGB_PARAMS = {
    "n_estimators": 100,
    "max_depth": 5,
    "learning_rate": 0.1,
    "random_state": 42,
    "tree_method": "hist"
}

RAIN_BINS = [
    ("0–10 mm", lambda r: (r >= 0.0) & (r <= 10.0)),
    ("10–25 mm", lambda r: (r > 10.0) & (r <= 25.0)),
    ("25–50 mm", lambda r: (r > 25.0) & (r <= 50.0)),
    ("50–100 mm", lambda r: (r > 50.0) & (r <= 100.0)),
    (">100 mm", lambda r: (r > 100.0)),
]


def compute_classification_metrics(y_true_binary: np.ndarray, y_pred_binary: np.ndarray) -> dict:
    """Calculate confusion matrix and standard binary classification metrics."""
    tn, fp, fn, tp = confusion_matrix(y_true_binary, y_pred_binary).ravel()
    prec = float(precision_score(y_true_binary, y_pred_binary, zero_division=0))
    rec = float(recall_score(y_true_binary, y_pred_binary, zero_division=0))
    f1 = float(f1_score(y_true_binary, y_pred_binary, zero_division=0))
    acc = float(accuracy_score(y_true_binary, y_pred_binary))
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    bal_acc = float(balanced_accuracy_score(y_true_binary, y_pred_binary))
    mcc = float(matthews_corrcoef(y_true_binary, y_pred_binary))

    return {
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "accuracy": round(acc, 4),
        "specificity": round(spec, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "matthews_corrcoef": round(mcc, 4),
    }


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate standard regression metrics: MAE, RMSE, mean bias, median AE, max AE."""
    res = y_pred - y_true
    abs_res = np.abs(res)
    return {
        "sample_count": int(len(y_true)),
        "mae": round(float(np.mean(abs_res)), 4),
        "rmse": round(float(np.sqrt(np.mean(res**2))), 4),
        "mean_bias": round(float(np.mean(res)), 4),
        "median_absolute_error": round(float(np.median(abs_res)), 4),
        "max_absolute_error": round(float(np.max(abs_res)), 4),
    }


def compute_conformal_metrics(
    y_test: np.ndarray,
    cqr_lower: np.ndarray,
    cqr_upper: np.ndarray,
    is_bust_true: np.ndarray
) -> dict:
    """Compute Split Conformal Prediction empirical coverage and width statistics."""
    covered = (y_test >= cqr_lower) & (y_test <= cqr_upper)
    widths = cqr_upper - cqr_lower
    emp_cov = round(float(np.mean(covered) * 100.0), 2)
    mean_w = round(float(np.mean(widths)), 4)
    median_w = round(float(np.median(widths)), 4)
    min_w = round(float(np.min(widths)), 4)
    max_w = round(float(np.max(widths)), 4)

    is_bust_bool = is_bust_true.astype(bool)
    cov_bust = round(float(np.mean(covered[is_bust_bool]) * 100.0), 2) if is_bust_bool.sum() > 0 else 0.0
    cov_non_bust = round(float(np.mean(covered[~is_bust_bool]) * 100.0), 2) if (~is_bust_bool).sum() > 0 else 0.0

    return {
        "method": "Split Conformal Prediction (MAPIE SplitConformalRegressor)",
        "nominal_coverage_pct": 80.0,
        "empirical_coverage_pct": emp_cov,
        "mean_interval_width": mean_w,
        "median_interval_width": median_w,
        "min_interval_width": min_w,
        "max_interval_width": max_w,
        "bust_cases_diagnostic": {
            "sample_count": int(is_bust_bool.sum()),
            "empirical_coverage_pct": cov_bust,
            "mean_interval_width": round(float(np.mean(widths[is_bust_bool])), 4) if is_bust_bool.sum() > 0 else 0.0,
            "median_interval_width": round(float(np.median(widths[is_bust_bool])), 4) if is_bust_bool.sum() > 0 else 0.0,
            "diagnostic_note": (
                "Diagnostic subgroup calculation only. Split conformal prediction guarantees apply marginally "
                "under exchangeability across the general sample space, not conditionally to post-hoc subsets "
                "selected by extreme forecast errors (>25 mm)."
            ),
        },
        "non_bust_cases_diagnostic": {
            "sample_count": int((~is_bust_bool).sum()),
            "empirical_coverage_pct": cov_non_bust,
            "mean_interval_width": round(float(np.mean(widths[~is_bust_bool])), 4) if (~is_bust_bool).sum() > 0 else 0.0,
            "median_interval_width": round(float(np.median(widths[~is_bust_bool])), 4) if (~is_bust_bool).sum() > 0 else 0.0,
            "diagnostic_note": "Diagnostic subgroup calculation only.",
        },
    }


def compute_intensity_stratification(
    o_rain: np.ndarray,
    y_test: np.ndarray,
    raw_pred: np.ndarray,
    is_bust_true: np.ndarray
) -> dict:
    """Stratify regression and bust metrics by observed rainfall intensity bins."""
    strat_results = {}
    total_test = len(y_test)
    accum_samples = 0

    for name, mask_fn in RAIN_BINS:
        mask = mask_fn(o_rain)
        cnt = int(mask.sum())
        accum_samples += cnt
        if cnt > 0:
            reg = compute_regression_metrics(y_test[mask], raw_pred[mask])
            busts_in_bin = int(is_bust_true[mask].sum())
            strat_results[name] = {
                "sample_count": cnt,
                "pct_of_test_set": round(float(cnt / total_test * 100.0), 2),
                "mae": reg["mae"],
                "rmse": reg["rmse"],
                "mean_bias": reg["mean_bias"],
                "bust_count": busts_in_bin,
                "bust_prevalence_pct": round(float(busts_in_bin / cnt * 100.0), 2),
            }
        else:
            strat_results[name] = {
                "sample_count": 0,
                "pct_of_test_set": 0.0,
                "mae": 0.0,
                "rmse": 0.0,
                "mean_bias": 0.0,
                "bust_count": 0,
                "bust_prevalence_pct": 0.0,
            }

    assert accum_samples == total_test, f"Stratification count mismatch: {accum_samples} != {total_test}"
    return strat_results


def evaluate_model_pipeline(
    train_df: pd.DataFrame,
    calib_df: pd.DataFrame,
    test_df: pd.DataFrame,
    context_label: str
) -> dict:
    """Train XGBoost, calibrate Split Conformal, and evaluate test set comprehensively."""
    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL].values
    X_calib, y_calib = calib_df[FEATURE_COLS], calib_df[TARGET_COL].values
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL].values

    f_apcp = test_df["f_apcp_24h"].values
    o_rain = test_df["o_rain_24h"].values
    is_bust_true = test_df["is_bust"].values.astype(int)

    # 1. Baseline: Median-error baseline strictly from training set
    baseline_median = float(np.median(y_train))
    baseline_pred = np.full(len(y_test), baseline_median)
    base_mae = float(mean_absolute_error(y_test, baseline_pred))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_pred)))

    # 2. Train XGBoost
    base_model = xgb.XGBRegressor(**XGB_PARAMS)
    base_model.fit(X_train, y_train)
    raw_pred = base_model.predict(X_test)

    xgb_mae = float(mean_absolute_error(y_test, raw_pred))
    xgb_rmse = float(np.sqrt(mean_squared_error(y_test, raw_pred)))
    mae_imp = round(((base_mae - xgb_mae) / base_mae) * 100.0, 2)
    rmse_imp = round(((base_rmse - xgb_rmse) / base_rmse) * 100.0, 2)

    # 3. Conformalize SplitConformalRegressor
    conformal_reg = SplitConformalRegressor(
        estimator=base_model,
        confidence_level=0.80,
        prefit=True
    )
    conformal_reg.conformalize(X_calib, y_calib)

    _, intervals = conformal_reg.predict_interval(X_test)
    cqr_lower = np.maximum(intervals[:, 0, 0], 0.0)
    cqr_upper = intervals[:, 1, 0]

    # Derived bust risk score using established repository formula
    pred_error_clamped = np.maximum(raw_pred, 0.0)
    risk_score = np.clip(
        (pred_error_clamped / 35.0) + np.where(cqr_upper > 25.0, 0.15, 0.0),
        0.01,
        0.98,
    )

    # 4. Bust Detection Decision Rules
    # Rule A: Forecast-side predicted-error alert rule (operational approximation)
    pred_bust_a = ((raw_pred > 25.0) & (f_apcp > 10.0)).astype(int)
    class_a = compute_classification_metrics(is_bust_true, pred_bust_a)

    # Rule B: Established operational alert threshold (derived bust risk score >= 0.70)
    pred_bust_b = (risk_score >= 0.70).astype(int)
    class_b = compute_classification_metrics(is_bust_true, pred_bust_b)

    # Rule C: Conformal upper bound exceeding 25 mm (cqr_upper > 25.0 mm)
    pred_bust_c = (cqr_upper > 25.0).astype(int)
    class_c = compute_classification_metrics(is_bust_true, pred_bust_c)

    # Verify confusion matrix sums
    assert class_a["tp"] + class_a["tn"] + class_a["fp"] + class_a["fn"] == len(test_df)
    assert class_b["tp"] + class_b["tn"] + class_b["fp"] + class_b["fn"] == len(test_df)
    assert class_c["tp"] + class_c["tn"] + class_c["fp"] + class_c["fn"] == len(test_df)

    # 5. Regression Metrics
    reg_overall = compute_regression_metrics(y_test, raw_pred)
    is_bust_bool = is_bust_true.astype(bool)
    reg_bust = compute_regression_metrics(y_test[is_bust_bool], raw_pred[is_bust_bool]) if is_bust_bool.sum() > 0 else {}
    reg_non_bust = compute_regression_metrics(y_test[~is_bust_bool], raw_pred[~is_bust_bool]) if (~is_bust_bool).sum() > 0 else {}

    # 6. Conformal Metrics
    conf_metrics = compute_conformal_metrics(y_test, cqr_lower, cqr_upper, is_bust_true)

    # 7. Rainfall Intensity Stratification
    strat_metrics = compute_intensity_stratification(o_rain, y_test, raw_pred, is_bust_true)

    return {
        "context_label": context_label,
        "sample_counts": {
            "train": len(train_df),
            "calib": len(calib_df),
            "test": len(test_df),
            "test_busts": int(is_bust_true.sum()),
            "test_bust_prevalence_pct": round(float(is_bust_true.mean() * 100.0), 2),
        },
        "regression": {
            "baseline": {
                "name": "Median Error Baseline (Train Set)",
                "median_error_mm": round(baseline_median, 4),
                "mae": round(base_mae, 4),
                "rmse": round(base_rmse, 4),
            },
            "overall_test": {
                "mae": reg_overall["mae"],
                "rmse": reg_overall["rmse"],
                "mean_bias": reg_overall["mean_bias"],
                "median_absolute_error": reg_overall["median_absolute_error"],
                "max_absolute_error": reg_overall["max_absolute_error"],
                "mae_improvement_pct": mae_imp,
                "rmse_improvement_pct": rmse_imp,
            },
            "bust_cases": reg_bust,
            "non_bust_cases": reg_non_bust,
        },
        "conformal": conf_metrics,
        "bust_detection": {
            "rule_a": {
                "label": "Rule A: predicted_error > 25 mm & forecast > 10 mm",
                "nature": "operational approximation; not identical to the ground-truth bust rule",
                "metrics": class_a,
            },
            "rule_b": {
                "label": "Rule B: derived bust risk score >= 0.70",
                "nature": "derived bust risk score; model-based risk indicator, not a calibrated probability",
                "metrics": class_b,
            },
            "rule_c": {
                "label": "Rule C: conformal upper bound > 25 mm",
                "nature": "80% split conformal prediction interval upper bound exceeding 25 mm",
                "metrics": class_c,
            },
        },
        "rainfall_stratification": strat_metrics,
    }


def partition_month_dataframe(df: pd.DataFrame, month_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Sort and partition a 30-day monthly feature matrix into train (20d), calib (5d), test (5d)."""
    df_sorted = df.sort_values("valid_time").reset_index(drop=True)
    unique_dates = df_sorted["valid_time"].drop_duplicates().sort_values().tolist()
    assert len(unique_dates) == 30, f"{month_name} expected 30 unique valid dates, found {len(unique_dates)}"

    train_dates = unique_dates[:20]
    calib_dates = unique_dates[20:25]
    test_dates = unique_dates[25:]

    train_df = df_sorted[df_sorted["valid_time"].isin(train_dates)].copy().reset_index(drop=True)
    calib_df = df_sorted[df_sorted["valid_time"].isin(calib_dates)].copy().reset_index(drop=True)
    test_df = df_sorted[df_sorted["valid_time"].isin(test_dates)].copy().reset_index(drop=True)

    assert len(train_df) == 98100, f"{month_name} train count mismatch: {len(train_df)}"
    assert len(calib_df) == 24525, f"{month_name} calib count mismatch: {len(calib_df)}"
    assert len(test_df) == 24525, f"{month_name} test count mismatch: {len(test_df)}"

    assert train_df["valid_time"].max() < calib_df["valid_time"].min(), f"{month_name} train/calib temporal violation"
    assert calib_df["valid_time"].max() < test_df["valid_time"].min(), f"{month_name} calib/test temporal violation"

    return train_df, calib_df, test_df


def check_finite(obj, path=""):
    """Recursively verify all numerical values in metrics dictionary are finite."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_finite(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float, np.integer, np.floating)):
        assert np.isfinite(obj), f"Non-finite value at {path}: {obj}"


def main():
    print("=" * 75)
    print("VISHWAS PHASE 1B: COMPLETE MULTI-MONTH VALIDATION PACKAGE")
    print("=" * 75)

    base_dir = Path("backend/data/real/features")
    july_path = base_dir / "july_2023_matrix.parquet"
    august_path = base_dir / "august_2023_matrix.parquet"
    september_path = base_dir / "september_2023_matrix.parquet"

    aug_phase1a_json = Path("ml_pipeline/real_data/aug2023_d1_validation_metrics.json")
    assert july_path.exists(), f"July matrix missing: {july_path}"
    assert august_path.exists(), f"August matrix missing: {august_path}"
    assert september_path.exists(), f"September matrix missing: {september_path}"
    assert aug_phase1a_json.exists(), f"Phase 1A August metrics JSON missing: {aug_phase1a_json}"

    print(f"\n[DATA] Loading July 2023 matrix:      {july_path}")
    july_raw = pd.read_parquet(july_path)
    print(f"[DATA] Loading August 2023 matrix:    {august_path}")
    august_raw = pd.read_parquet(august_path)
    print(f"[DATA] Loading September 2023 matrix: {september_path}")
    september_raw = pd.read_parquet(september_path)

    # 1. Partition each month
    print("\n[PARTITION] Chronological partitioning (20 train / 5 calib / 5 test):")
    j_train, j_calib, j_test = partition_month_dataframe(july_raw, "July 2023")
    a_train, a_calib, a_test = partition_month_dataframe(august_raw, "August 2023")
    s_train, s_calib, s_test = partition_month_dataframe(september_raw, "September 2023")

    print(f"  July 2023:      Train {j_train['valid_time'].min().strftime('%Y-%m-%d')} to {j_train['valid_time'].max().strftime('%Y-%m-%d')} ({len(j_train):,}) | "
          f"Calib {j_calib['valid_time'].min().strftime('%Y-%m-%d')} to {j_calib['valid_time'].max().strftime('%Y-%m-%d')} ({len(j_calib):,}) | "
          f"Test {j_test['valid_time'].min().strftime('%Y-%m-%d')} to {j_test['valid_time'].max().strftime('%Y-%m-%d')} ({len(j_test):,})")
    print(f"  August 2023:    Train {a_train['valid_time'].min().strftime('%Y-%m-%d')} to {a_train['valid_time'].max().strftime('%Y-%m-%d')} ({len(a_train):,}) | "
          f"Calib {a_calib['valid_time'].min().strftime('%Y-%m-%d')} to {a_calib['valid_time'].max().strftime('%Y-%m-%d')} ({len(a_calib):,}) | "
          f"Test {a_test['valid_time'].min().strftime('%Y-%m-%d')} to {a_test['valid_time'].max().strftime('%Y-%m-%d')} ({len(a_test):,})")
    print(f"  September 2023: Train {s_train['valid_time'].min().strftime('%Y-%m-%d')} to {s_train['valid_time'].max().strftime('%Y-%m-%d')} ({len(s_train):,}) | "
          f"Calib {s_calib['valid_time'].min().strftime('%Y-%m-%d')} to {s_calib['valid_time'].max().strftime('%Y-%m-%d')} ({len(s_calib):,}) | "
          f"Test {s_test['valid_time'].min().strftime('%Y-%m-%d')} to {s_test['valid_time'].max().strftime('%Y-%m-%d')} ({len(s_test):,})")

    # =========================================================================
    # EXPERIMENT A: MONTH-BY-MONTH REPLICATION
    # =========================================================================
    print("\n" + "=" * 75)
    print("EXPERIMENT A: MONTH-BY-MONTH REPLICATION")
    print("=" * 75)

    print("\n[EXP A] Training and evaluating July 2023...")
    exp_a_july = evaluate_model_pipeline(j_train, j_calib, j_test, "July 2023 Replication")

    print("[EXP A] Ingesting authoritative Phase 1A August 2023 baseline...")
    with open(aug_phase1a_json, "r", encoding="utf-8") as f:
        aug_phase1a_raw = json.load(f)

    # Compute intensity stratification for August with bust_count and bust_prevalence_pct for uniformity
    aug_o_rain = a_test["o_rain_24h"].values
    aug_y_test = a_test["error_abs"].values
    aug_f_apcp = a_test["f_apcp_24h"].values
    aug_is_bust = a_test["is_bust"].values.astype(int)

    # Load August model for any helper predictions if required
    aug_model_pkl = Path("backend/data/real/models/cqr_model.pkl")
    with open(aug_model_pkl, "rb") as f:
        aug_art = pickle.load(f)
    aug_pred = aug_art["xgboost_model"].predict(a_test[FEATURE_COLS])
    aug_strat = compute_intensity_stratification(aug_o_rain, aug_y_test, aug_pred, aug_is_bust)

    exp_a_august = {
        "context_label": "August 2023 Phase 1A Authoritative Baseline",
        "sample_counts": {
            "train": 98100,
            "calib": 24525,
            "test": 24525,
            "test_busts": 470,
            "test_bust_prevalence_pct": 1.92,
        },
        "regression": {
            "baseline": aug_phase1a_raw["regression_metrics"]["baseline"],
            "overall_test": aug_phase1a_raw["regression_metrics"]["overall_test"],
            "bust_cases": aug_phase1a_raw["regression_metrics"]["bust_cases"],
            "non_bust_cases": aug_phase1a_raw["regression_metrics"]["non_bust_cases"],
        },
        "conformal": {
            "method": aug_phase1a_raw["conformal_metrics"]["method"],
            "nominal_coverage_pct": aug_phase1a_raw["conformal_metrics"]["nominal_coverage_pct"],
            "empirical_coverage_pct": aug_phase1a_raw["conformal_metrics"]["empirical_coverage_pct"],
            "mean_interval_width": aug_phase1a_raw["conformal_metrics"]["mean_interval_width"],
            "median_interval_width": aug_phase1a_raw["conformal_metrics"]["median_interval_width"],
            "min_interval_width": round(float(np.min(aug_art["conformal_regressor"].predict_interval(a_test[FEATURE_COLS])[1][:, 1, 0] - np.maximum(aug_art["conformal_regressor"].predict_interval(a_test[FEATURE_COLS])[1][:, 0, 0], 0.0))), 4),
            "max_interval_width": round(float(np.max(aug_art["conformal_regressor"].predict_interval(a_test[FEATURE_COLS])[1][:, 1, 0] - np.maximum(aug_art["conformal_regressor"].predict_interval(a_test[FEATURE_COLS])[1][:, 0, 0], 0.0))), 4),
            "bust_cases_diagnostic": aug_phase1a_raw["conformal_metrics"]["bust_cases_diagnostic"],
            "non_bust_cases_diagnostic": aug_phase1a_raw["conformal_metrics"]["non_bust_cases_diagnostic"],
        },
        "bust_detection": {
            "rule_a": {
                "label": "Rule A: predicted_error > 25 mm & forecast > 10 mm",
                "nature": "operational approximation; not identical to the ground-truth bust rule",
                "metrics": aug_phase1a_raw["bust_metrics"]["primary_decision_rule"]["metrics"],
            },
            "rule_b": {
                "label": "Rule B: derived bust risk score >= 0.70",
                "nature": "derived bust risk score; model-based risk indicator, not a calibrated probability",
                "metrics": aug_phase1a_raw["bust_metrics"]["operational_alert_rule"]["metrics"],
            },
            "rule_c": {
                "label": "Rule C: conformal upper bound > 25 mm",
                "nature": "80% split conformal prediction interval upper bound exceeding 25 mm",
                "metrics": aug_phase1a_raw["bust_metrics"]["conformal_upper_bound_rule"]["metrics"],
            },
        },
        "rainfall_stratification": aug_strat,
    }

    print("[EXP A] Training and evaluating September 2023...")
    exp_a_september = evaluate_model_pipeline(s_train, s_calib, s_test, "September 2023 Replication")

    # =========================================================================
    # EXPERIMENT B: POOLED THREE-MONTH MODEL
    # =========================================================================
    print("\n" + "=" * 75)
    print("EXPERIMENT B: POOLED THREE-MONTH RETROSPECTIVE EVALUATION")
    print("=" * 75)

    pooled_train = pd.concat([j_train, a_train, s_train], ignore_index=True)
    pooled_calib = pd.concat([j_calib, a_calib, s_calib], ignore_index=True)
    pooled_test = pd.concat([j_test, a_test, s_test], ignore_index=True)

    assert len(pooled_train) == 294300, f"Pooled train count mismatch: {len(pooled_train)}"
    assert len(pooled_calib) == 73575, f"Pooled calib count mismatch: {len(pooled_calib)}"
    assert len(pooled_test) == 73575, f"Pooled test count mismatch: {len(pooled_test)}"

    print(f"[EXP B] Fitting pooled model (Train={len(pooled_train):,}, Calib={len(pooled_calib):,}, Test={len(pooled_test):,})...")
    # Train pooled model
    X_p_train, y_p_train = pooled_train[FEATURE_COLS], pooled_train[TARGET_COL].values
    X_p_calib, y_p_calib = pooled_calib[FEATURE_COLS], pooled_calib[TARGET_COL].values

    p_base_model = xgb.XGBRegressor(**XGB_PARAMS)
    p_base_model.fit(X_p_train, y_p_train)

    p_conformal = SplitConformalRegressor(estimator=p_base_model, confidence_level=0.80, prefit=True)
    p_conformal.conformalize(X_p_calib, y_p_calib)

    def evaluate_with_prefitted(m, conf, test_slice, label, train_target_median):
        X_t, y_t = test_slice[FEATURE_COLS], test_slice[TARGET_COL].values
        f_ap = test_slice["f_apcp_24h"].values
        o_rn = test_slice["o_rain_24h"].values
        is_b = test_slice["is_bust"].values.astype(int)

        r_pred = m.predict(X_t)
        _, ints = conf.predict_interval(X_t)
        low = np.maximum(ints[:, 0, 0], 0.0)
        up = ints[:, 1, 0]

        r_clamped = np.maximum(r_pred, 0.0)
        r_score = np.clip((r_clamped / 35.0) + np.where(up > 25.0, 0.15, 0.0), 0.01, 0.98)

        base_pred = np.full(len(y_t), train_target_median)
        b_mae = float(mean_absolute_error(y_t, base_pred))
        b_rmse = float(np.sqrt(mean_squared_error(y_t, base_pred)))
        x_mae = float(mean_absolute_error(y_t, r_pred))
        x_rmse = float(np.sqrt(mean_squared_error(y_t, r_pred)))

        pa = ((r_pred > 25.0) & (f_ap > 10.0)).astype(int)
        pb = (r_score >= 0.70).astype(int)
        pc = (up > 25.0).astype(int)

        reg_all = compute_regression_metrics(y_t, r_pred)
        conf_met = compute_conformal_metrics(y_t, low, up, is_b)
        strat = compute_intensity_stratification(o_rn, y_t, r_pred, is_b)

        return {
            "context_label": label,
            "sample_counts": {
                "test": len(test_slice),
                "test_busts": int(is_b.sum()),
                "test_bust_prevalence_pct": round(float(is_b.mean() * 100.0), 2),
            },
            "regression": {
                "baseline": {
                    "median_error_mm": round(train_target_median, 4),
                    "mae": round(b_mae, 4),
                    "rmse": round(b_rmse, 4),
                },
                "overall_test": {
                    "mae": reg_all["mae"],
                    "rmse": reg_all["rmse"],
                    "mean_bias": reg_all["mean_bias"],
                    "median_absolute_error": reg_all["median_absolute_error"],
                    "max_absolute_error": reg_all["max_absolute_error"],
                    "mae_improvement_pct": round(((b_mae - x_mae) / b_mae) * 100.0, 2),
                    "rmse_improvement_pct": round(((b_rmse - x_rmse) / b_rmse) * 100.0, 2),
                },
            },
            "conformal": conf_met,
            "bust_detection": {
                "rule_a": {
                    "label": "Rule A: predicted_error > 25 mm & forecast > 10 mm",
                    "metrics": compute_classification_metrics(is_b, pa),
                },
                "rule_b": {
                    "label": "Rule B: derived bust risk score >= 0.70",
                    "metrics": compute_classification_metrics(is_b, pb),
                },
                "rule_c": {
                    "label": "Rule C: conformal upper bound > 25 mm",
                    "metrics": compute_classification_metrics(is_b, pc),
                },
            },
            "rainfall_stratification": strat,
        }

    pooled_median_error = float(np.median(y_p_train))
    exp_b_combined = evaluate_with_prefitted(p_base_model, p_conformal, pooled_test, "Pooled Combined Test Set (15 days, 73,575 rows)", pooled_median_error)
    exp_b_july_slice = evaluate_with_prefitted(p_base_model, p_conformal, j_test, "Pooled Model on July Test Set (5 days, 24,525 rows)", pooled_median_error)
    exp_b_august_slice = evaluate_with_prefitted(p_base_model, p_conformal, a_test, "Pooled Model on August Test Set (5 days, 24,525 rows)", pooled_median_error)
    exp_b_september_slice = evaluate_with_prefitted(p_base_model, p_conformal, s_test, "Pooled Model on September Test Set (5 days, 24,525 rows)", pooled_median_error)

    # =========================================================================
    # EXPERIMENT C: RETROSPECTIVE CROSS-MONTH TRANSFER
    # =========================================================================
    print("\n" + "=" * 75)
    print("EXPERIMENT C: RETROSPECTIVE CROSS-MONTH TRANSFER (LEAVE-ONE-MONTH-OUT)")
    print("=" * 75)

    # Case 1: Hold out July (Train on Aug+Sept, Calib on Aug+Sept, Test on July)
    print("\n[EXP C - Case 1] Hold out July: Train on August+September...")
    c1_train = pd.concat([a_train, s_train], ignore_index=True)
    c1_calib = pd.concat([a_calib, s_calib], ignore_index=True)
    c1_test = j_test
    exp_c_case1 = evaluate_model_pipeline(c1_train, c1_calib, c1_test, "Case 1: Hold Out July (Train: Aug+Sept)")

    # Case 2: Hold out August (Train on July+Sept, Calib on July+Sept, Test on August)
    print("[EXP C - Case 2] Hold out August: Train on July+September...")
    c2_train = pd.concat([j_train, s_train], ignore_index=True)
    c2_calib = pd.concat([j_calib, s_calib], ignore_index=True)
    c2_test = a_test
    exp_c_case2 = evaluate_model_pipeline(c2_train, c2_calib, c2_test, "Case 2: Hold Out August (Train: July+Sept)")

    # Case 3: Hold out September (Train on July+Aug, Calib on July+Aug, Test on September)
    print("[EXP C - Case 3] Hold out September: Train on July+August...")
    c3_train = pd.concat([j_train, a_train], ignore_index=True)
    c3_calib = pd.concat([j_calib, a_calib], ignore_index=True)
    c3_test = s_test
    exp_c_case3 = evaluate_model_pipeline(c3_train, c3_calib, c3_test, "Case 3: Hold Out September (Train: July+Aug)")

    # Assemble Structured JSON Payload
    full_payload = {
        "metadata": {
            "evaluation_title": "VISHWAS Phase 1B: Multi-Month Real-Data Validation",
            "cycle": "00:00 UTC cycle, D+1 forecast lead (+3h to +27h accumulation difference)",
            "nwp_source": "NOAA Global Forecast System (GFS) 0.25° Open Data",
            "obs_source": "India Meteorological Department (IMD) 0.25° Gridded Daily Rainfall",
            "active_cells_per_day": 4905,
            "feature_columns": FEATURE_COLS,
            "target_column": TARGET_COL,
            "conformal_method": "Split Conformal Prediction (MAPIE SplitConformalRegressor)",
            "nominal_coverage_pct": 80.0,
            "hyperparameters": XGB_PARAMS,
            "bust_truth_formula": "ABS(F - O) > 25.0 mm AND (F > 10.0 mm OR O > 10.0 mm)",
        },
        "datasets": {
            "july_2023": {
                "period": "July 2, 2023 – July 31, 2023",
                "total_rows": len(july_raw),
                "total_busts": int(july_raw["is_bust"].sum()),
                "total_bust_prevalence_pct": round(float(july_raw["is_bust"].mean() * 100.0), 2),
            },
            "august_2023": {
                "period": "August 2, 2023 – August 31, 2023",
                "total_rows": len(august_raw),
                "total_busts": int(august_raw["is_bust"].sum()),
                "total_bust_prevalence_pct": round(float(august_raw["is_bust"].mean() * 100.0), 2),
            },
            "september_2023": {
                "period": "September 1, 2023 – September 30, 2023",
                "total_rows": len(september_raw),
                "total_busts": int(september_raw["is_bust"].sum()),
                "total_bust_prevalence_pct": round(float(september_raw["is_bust"].mean() * 100.0), 2),
            },
        },
        "experiment_a_monthly_replication": {
            "july_2023": exp_a_july,
            "august_2023": exp_a_august,
            "september_2023": exp_a_september,
        },
        "experiment_b_pooled_model": {
            "combined_test": exp_b_combined,
            "subsets": {
                "july_test_subset": exp_b_july_slice,
                "august_test_subset": exp_b_august_slice,
                "september_test_subset": exp_b_september_slice,
            },
        },
        "experiment_c_cross_month_transfer": {
            "case_1_hold_out_july": exp_c_case1,
            "case_2_hold_out_august": exp_c_case2,
            "case_3_hold_out_september": exp_c_case3,
        },
    }

    # Verify that all numbers are finite
    check_finite(full_payload)

    # Save to JSON
    out_json = Path("ml_pipeline/real_data/phase1b_multimonth_metrics.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(full_payload, f, indent=2)

    print(f"\n[DONE] Successfully saved Phase 1B multi-month metrics to: {out_json}")

    # =========================================================================
    # PRINT CONSOLE TABLES AS REQUIRED
    # =========================================================================
    print("\n" + "=" * 90)
    print("TABLE 1 — DATASET")
    print("=" * 90)
    print(f"{'Month':<12} | {'Rows':<8} | {'Test Rows':<10} | {'Bust Count':<11} | {'Bust Prevalence':<15}")
    print("-" * 65)
    for m_label, df_raw, test_s in [("July", july_raw, j_test), ("August", august_raw, a_test), ("September", september_raw, s_test)]:
        b_cnt = int(df_raw["is_bust"].sum())
        b_prev = df_raw["is_bust"].mean() * 100.0
        print(f"{m_label:<12} | {len(df_raw):<8,} | {len(test_s):<10,} | {b_cnt:<11,} | {b_prev:.2f}%")

    print("\n" + "=" * 105)
    print("TABLE 2 — MONTHLY REGRESSION (EXPERIMENT A)")
    print("=" * 105)
    print(f"{'Month':<12} | {'Baseline MAE':<13} | {'XGB MAE':<10} | {'Baseline RMSE':<14} | {'XGB RMSE':<10} | {'MAE Imp %':<10} | {'RMSE Imp %':<11} | {'Bias':<8}")
    print("-" * 105)
    for m_label, res in [("July", exp_a_july), ("August", exp_a_august), ("September", exp_a_september)]:
        b = res["regression"]["baseline"]
        x = res["regression"]["overall_test"]
        print(f"{m_label:<12} | {b['mae']:<13.4f} | {x['mae']:<10.4f} | {b['rmse']:<14.4f} | {x['rmse']:<10.4f} | {x['mae_improvement_pct']:<10.2f} | {x['rmse_improvement_pct']:<11.2f} | {x['mean_bias']:<8.4f}")

    print("\n" + "=" * 80)
    print("TABLE 3 — CONFORMAL (EXPERIMENT A)")
    print("=" * 80)
    print(f"{'Month':<12} | {'Nominal Cov':<12} | {'Empirical Cov':<14} | {'Mean Width':<12} | {'Median Width':<12}")
    print("-" * 75)
    for m_label, res in [("July", exp_a_july), ("August", exp_a_august), ("September", exp_a_september)]:
        c = res["conformal"]
        print(f"{m_label:<12} | {c['nominal_coverage_pct']:<12.1f}% | {c['empirical_coverage_pct']:<14.2f}% | {c['mean_interval_width']:<12.4f} | {c['median_interval_width']:<12.4f}")

    print("\n" + "=" * 115)
    print("TABLE 4 — BUST RULES (EXPERIMENT A)")
    print("=" * 115)
    print(f"{'Month':<10} | {'Rule':<8} | {'TP':<6} | {'FP':<6} | {'TN':<7} | {'FN':<6} | {'Precision':<10} | {'Recall':<8} | {'F1':<8} | {'Bal Acc':<8} | {'MCC':<8}")
    print("-" * 115)
    for m_label, res in [("July", exp_a_july), ("August", exp_a_august), ("September", exp_a_september)]:
        for r_code, r_key in [("Rule A", "rule_a"), ("Rule B", "rule_b"), ("Rule C", "rule_c")]:
            m = res["bust_detection"][r_key]["metrics"]
            print(f"{m_label:<10} | {r_code:<8} | {m['tp']:<6} | {m['fp']:<6} | {m['tn']:<7} | {m['fn']:<6} | {m['precision']:<10.4f} | {m['recall']:<8.4f} | {m['f1_score']:<8.4f} | {m['balanced_accuracy']:<8.4f} | {m['matthews_corrcoef']:<8.4f}")

    print("\n" + "=" * 90)
    print("TABLE 5 — INTENSITY (EXPERIMENT A)")
    print("=" * 90)
    print(f"{'Month':<10} | {'Rainfall Bin':<12} | {'N':<7} | {'MAE':<8} | {'RMSE':<8} | {'Bias':<8} | {'Bust Prev %':<12}")
    print("-" * 80)
    for m_label, res in [("July", exp_a_july), ("August", exp_a_august), ("September", exp_a_september)]:
        for b_name in ["0–10 mm", "10–25 mm", "25–50 mm", "50–100 mm", ">100 mm"]:
            st = res["rainfall_stratification"][b_name]
            print(f"{m_label:<10} | {b_name:<12} | {st['sample_count']:<7} | {st['mae']:<8.4f} | {st['rmse']:<8.4f} | {st['mean_bias']:<8.4f} | {st['bust_prevalence_pct']:<12.2f}%")

    print("\n" + "=" * 105)
    print("TABLE 6 — POOLED MODEL (EXPERIMENT B)")
    print("=" * 105)
    print(f"{'Target Month':<18} | {'Test N':<8} | {'MAE':<8} | {'RMSE':<8} | {'Bias':<8} | {'Coverage':<9} | {'Rule A F1':<10} | {'Rule B F1':<10} | {'Rule C F1':<10}")
    print("-" * 105)
    for t_name, sub in [
        ("Combined (3-Mo)", exp_b_combined),
        ("July Subset", exp_b_july_slice),
        ("August Subset", exp_b_august_slice),
        ("September Subset", exp_b_september_slice),
    ]:
        reg = sub["regression"]["overall_test"]
        cov = sub["conformal"]["empirical_coverage_pct"]
        f1_a = sub["bust_detection"]["rule_a"]["metrics"]["f1_score"]
        f1_b = sub["bust_detection"]["rule_b"]["metrics"]["f1_score"]
        f1_c = sub["bust_detection"]["rule_c"]["metrics"]["f1_score"]
        print(f"{t_name:<18} | {sub['sample_counts']['test']:<8,} | {reg['mae']:<8.4f} | {reg['rmse']:<8.4f} | {reg['mean_bias']:<8.4f} | {cov:<9.2f}% | {f1_a:<10.4f} | {f1_b:<10.4f} | {f1_c:<10.4f}")

    print("\n" + "=" * 115)
    print("TABLE 7 — CROSS-MONTH TRANSFER (EXPERIMENT C)")
    print("=" * 115)
    print(f"{'Held-Out Month':<16} | {'Training Months':<20} | {'Test N':<8} | {'MAE':<8} | {'RMSE':<8} | {'Coverage':<9} | {'Rule A F1':<10} | {'Rule B F1':<10} | {'Rule C F1':<10}")
    print("-" * 115)
    for h_name, tr_name, sub in [
        ("July 2023", "August + September", exp_c_case1),
        ("August 2023", "July + September", exp_c_case2),
        ("September 2023", "July + August", exp_c_case3),
    ]:
        reg = sub["regression"]["overall_test"]
        cov = sub["conformal"]["empirical_coverage_pct"]
        f1_a = sub["bust_detection"]["rule_a"]["metrics"]["f1_score"]
        f1_b = sub["bust_detection"]["rule_b"]["metrics"]["f1_score"]
        f1_c = sub["bust_detection"]["rule_c"]["metrics"]["f1_score"]
        print(f"{h_name:<16} | {tr_name:<20} | {sub['sample_counts']['test']:<8,} | {reg['mae']:<8.4f} | {reg['rmse']:<8.4f} | {cov:<9.2f}% | {f1_a:<10.4f} | {f1_b:<10.4f} | {f1_c:<10.4f}")

    print("\n" + "=" * 75)
    print("PHASE 1B EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 75)


if __name__ == "__main__":
    main()
