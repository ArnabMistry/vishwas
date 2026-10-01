"""VISHWAS Phase 2A: Medium-Range Real-Data Validation Evaluation (D1–D9).

This module performs the full evaluation of empirical medium-range forecast skill:
1. Loads monthly D2–D9 feature matrices (July, August, September 2023).
2. Incorporates authoritative D1 baseline metrics from Phase 1A / Phase 1B without retraining D1.
3. Evaluates 24 monthly lead models (3 months × 8 leads D2–D9) with exact initialization date partitions:
   - Train: first 20 initialization days (98,100 samples)
   - Calibration: next 5 initialization days (24,525 samples)
   - Test: final 5 initialization days (24,525 samples)
4. Evaluates 8 pooled multi-month lead models (D2 through D9):
   - Train: 294,300 samples (20 inits × 3 months)
   - Calibration: 73,575 samples (5 inits × 3 months)
   - Test: 73,575 samples (5 inits × 3 months)
   - Evaluated on combined test set and individual monthly test subsets.
5. Performs rainfall intensity stratification across 5 precipitation tiers for each lead.
6. Constructs the authoritative D1–D9 Reliability Profile (Table F).
7. Outputs structured metrics to ml_pipeline/real_data/phase2a_d1_d9_metrics.json.
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from mapie.regression import SplitConformalRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, confusion_matrix, matthews_corrcoef

# Reconfigure stdout/stderr for Windows console UTF-8 safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

FEATURE_COLS = [
    "f_apcp_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "lat",
    "lon",
]
TARGET_COL = "error_abs"

XGB_PARAMS = {
    "n_estimators": 100,
    "max_depth": 5,
    "learning_rate": 0.1,
    "random_state": 42,
    "tree_method": "hist",
}

# Exact initialization partitions
MONTH_SPLITS = {
    "july": {
        "train_end": "2023-07-20",
        "calib_start": "2023-07-21",
        "calib_end": "2023-07-25",
        "test_start": "2023-07-26",
        "test_end": "2023-07-30",
    },
    "august": {
        "train_end": "2023-08-20",
        "calib_start": "2023-08-21",
        "calib_end": "2023-08-25",
        "test_start": "2023-08-26",
        "test_end": "2023-08-30",
    },
    "september": {
        "train_end": "2023-09-19",
        "calib_start": "2023-09-20",
        "calib_end": "2023-09-24",
        "test_start": "2023-09-25",
        "test_end": "2023-09-29",
    },
}

RAIN_BINS = [
    ("0-10 mm", lambda r: (r >= 0.0) & (r <= 10.0)),
    ("10-25 mm", lambda r: (r > 10.0) & (r <= 25.0)),
    ("25-50 mm", lambda r: (r > 25.0) & (r <= 50.0)),
    ("50-100 mm", lambda r: (r > 50.0) & (r <= 100.0)),
    (">100 mm", lambda r: r > 100.0),
]


def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate complete classification suite."""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    bal_acc = (rec + spec) / 2.0
    mcc = float(matthews_corrcoef(y_true, y_pred)) if len(np.unique(y_true)) > 1 else 0.0

    return {
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "accuracy": round(float(acc), 4),
        "specificity": round(float(spec), 4),
        "balanced_accuracy": round(float(bal_acc), 4),
        "matthews_corrcoef": round(float(mcc), 4),
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
    is_bust_true: np.ndarray,
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


def evaluate_model_pipeline(
    train_df: pd.DataFrame,
    calib_df: pd.DataFrame,
    test_df: pd.DataFrame,
    context_label: str,
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

    # 2. Train XGBoost (7 predictors only, no lead_day/init_time)
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
        prefit=True,
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

    test_bust_count = int(is_bust_true.sum())
    test_bust_prev = round(float(test_bust_count / len(y_test) * 100.0), 2)

    return {
        "context_label": context_label,
        "sample_counts": {
            "train": int(len(train_df)),
            "calib": int(len(calib_df)),
            "test": int(len(test_df)),
            "test_busts": test_bust_count,
            "test_bust_prevalence_pct": test_bust_prev,
        },
        "regression": {
            "baseline": {
                "name": "Median Error Baseline (Train Set)",
                "median_error_mm": round(baseline_median, 4),
                "mae": round(base_mae, 4),
                "rmse": round(base_rmse, 4),
            },
            "overall_test": {
                "mae": round(xgb_mae, 4),
                "rmse": round(xgb_rmse, 4),
                "mean_bias": round(float(np.mean(raw_pred - y_test)), 4),
                "median_absolute_error": round(float(np.median(np.abs(raw_pred - y_test))), 4),
                "max_absolute_error": round(float(np.max(np.abs(raw_pred - y_test))), 4),
                "mae_improvement_pct": mae_imp,
                "rmse_improvement_pct": rmse_imp,
            },
        },
        "conformal": compute_conformal_metrics(y_test, cqr_lower, cqr_upper, is_bust_true),
        "bust_detection": {
            "rule_a": {
                "label": "Rule A: predicted_error > 25 mm & forecast > 10 mm (operational approximation)",
                "metrics": class_a,
            },
            "rule_b": {
                "label": "Rule B: derived bust risk score >= 0.70",
                "metrics": class_b,
            },
            "rule_c": {
                "label": "Rule C: conformal upper bound > 25 mm",
                "metrics": class_c,
            },
        },
        "_predictions": {
            "raw_pred": raw_pred,
            "y_test": y_test,
            "cqr_lower": cqr_lower,
            "cqr_upper": cqr_upper,
            "is_bust_true": is_bust_true,
            "f_apcp": f_apcp,
            "o_rain": o_rain,
        },
    }


def evaluate_subset_predictions(
    y_test: np.ndarray,
    raw_pred: np.ndarray,
    cqr_lower: np.ndarray,
    cqr_upper: np.ndarray,
    f_apcp: np.ndarray,
    is_bust_true: np.ndarray,
    baseline_median: float,
    context_label: str,
) -> dict:
    """Evaluate pre-fitted predictions on a subset without refitting."""
    base_pred = np.full(len(y_test), baseline_median)
    base_mae = float(mean_absolute_error(y_test, base_pred))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, base_pred)))

    xgb_mae = float(mean_absolute_error(y_test, raw_pred))
    xgb_rmse = float(np.sqrt(mean_squared_error(y_test, raw_pred)))
    mae_imp = round(((base_mae - xgb_mae) / base_mae) * 100.0, 2)
    rmse_imp = round(((base_rmse - xgb_rmse) / base_rmse) * 100.0, 2)

    pred_error_clamped = np.maximum(raw_pred, 0.0)
    risk_score = np.clip(
        (pred_error_clamped / 35.0) + np.where(cqr_upper > 25.0, 0.15, 0.0),
        0.01,
        0.98,
    )

    pred_bust_a = ((raw_pred > 25.0) & (f_apcp > 10.0)).astype(int)
    class_a = compute_classification_metrics(is_bust_true, pred_bust_a)

    pred_bust_b = (risk_score >= 0.70).astype(int)
    class_b = compute_classification_metrics(is_bust_true, pred_bust_b)

    pred_bust_c = (cqr_upper > 25.0).astype(int)
    class_c = compute_classification_metrics(is_bust_true, pred_bust_c)

    test_bust_count = int(is_bust_true.sum())
    test_bust_prev = round(float(test_bust_count / len(y_test) * 100.0), 2)

    return {
        "context_label": context_label,
        "sample_counts": {
            "test": int(len(y_test)),
            "test_busts": test_bust_count,
            "test_bust_prevalence_pct": test_bust_prev,
        },
        "regression": {
            "baseline": {
                "name": "Pooled Train Median Baseline",
                "median_error_mm": round(baseline_median, 4),
                "mae": round(base_mae, 4),
                "rmse": round(base_rmse, 4),
            },
            "overall_test": {
                "mae": round(xgb_mae, 4),
                "rmse": round(xgb_rmse, 4),
                "mean_bias": round(float(np.mean(raw_pred - y_test)), 4),
                "median_absolute_error": round(float(np.median(np.abs(raw_pred - y_test))), 4),
                "max_absolute_error": round(float(np.max(np.abs(raw_pred - y_test))), 4),
                "mae_improvement_pct": mae_imp,
                "rmse_improvement_pct": rmse_imp,
            },
        },
        "conformal": compute_conformal_metrics(y_test, cqr_lower, cqr_upper, is_bust_true),
        "bust_detection": {
            "rule_a": {
                "label": "Rule A: predicted_error > 25 mm & forecast > 10 mm",
                "metrics": class_a,
            },
            "rule_b": {
                "label": "Rule B: derived bust risk score >= 0.70",
                "metrics": class_b,
            },
            "rule_c": {
                "label": "Rule C: conformal upper bound > 25 mm",
                "metrics": class_c,
            },
        },
    }


def compute_intensity_stratification(o_rain: np.ndarray, y_test: np.ndarray, raw_pred: np.ndarray, is_bust_true: np.ndarray) -> dict:
    """Stratify regression and bust metrics across 5 rainfall tiers."""
    strat = {}
    total_test = len(y_test)
    for name, mask_fn in RAIN_BINS:
        mask = mask_fn(o_rain)
        cnt = int(mask.sum())
        if cnt > 0:
            reg = compute_regression_metrics(y_test[mask], raw_pred[mask])
            busts = int(is_bust_true[mask].sum())
            strat[name] = {
                "sample_count": cnt,
                "pct_of_test_set": round(float(cnt / total_test * 100.0), 2),
                "mae": reg["mae"],
                "rmse": reg["rmse"],
                "mean_bias": reg["mean_bias"],
                "bust_count": busts,
                "bust_prevalence_pct": round(float(busts / cnt * 100.0), 2),
            }
        else:
            strat[name] = {
                "sample_count": 0,
                "pct_of_test_set": 0.0,
                "mae": 0.0,
                "rmse": 0.0,
                "mean_bias": 0.0,
                "bust_count": 0,
                "bust_prevalence_pct": 0.0,
            }
    return strat


def load_authoritative_d1_metrics(phase1b_json_path: Path) -> dict:
    """Load authoritative Phase 1A / Phase 1B D1 metrics from existing artifact."""
    assert phase1b_json_path.exists(), f"Phase 1B metrics JSON missing: {phase1b_json_path}"
    with open(phase1b_json_path, "r") as f:
        p1b = json.load(f)

    # Monthly D1 metrics
    monthly_d1 = {}
    for m in ["july_2023", "august_2023", "september_2023"]:
        m_short = m.split("_")[0]
        monthly_d1[m_short] = p1b["experiment_a_monthly_replication"][m]

    # Pooled D1 metrics
    pooled_d1 = p1b["experiment_b_pooled_model"]

    return {
        "monthly": monthly_d1,
        "pooled": pooled_d1,
    }


def main():
    t_start = time.time()
    features_dir = Path("backend/data/real/features")
    metrics_out = Path("ml_pipeline/real_data/phase2a_d1_d9_metrics.json")
    phase1b_json = Path("ml_pipeline/real_data/phase1b_multimonth_metrics.json")

    print("\n" + "=" * 75)
    print("VISHWAS PHASE 2A: D1–D9 MEDIUM-RANGE REAL-DATA VALIDATION EVALUATION")
    print("=" * 75)

    # 1. Load Authoritative D1 Baseline Metrics
    print("[1/5] Loading Authoritative D1 Metrics from Phase 1B Artifact...")
    d1_authoritative = load_authoritative_d1_metrics(phase1b_json)
    print("      D1 metrics successfully loaded (no D1 recomputation).")

    # 2. Load D2–D9 Monthly Feature Matrices
    print("\n[2/5] Loading Monthly D2–D9 Feature Matrices...")
    datasets = {}
    for m in ["july", "august", "september"]:
        pq_path = features_dir / f"{m}_2023_d2_d9.parquet"
        assert pq_path.exists(), f"Missing matrix: {pq_path}"
        df = pd.read_parquet(str(pq_path))
        df["init_time"] = pd.to_datetime(df["init_time"])
        df["valid_time"] = pd.to_datetime(df["valid_time"])
        datasets[m] = df
        print(f"      {m.capitalize():<10}: {len(df):,} rows (8 leads, {df['init_time'].nunique()} init dates)")

    # 3. Monthly D2–D9 Model Evaluation (3 months × 8 leads = 24 models)
    print("\n[3/5] Training and Evaluating 24 Independent Monthly Lead Models (Part 10)...")
    monthly_results = {}
    for m in ["july", "august", "september"]:
        monthly_results[m] = {}
        splits = MONTH_SPLITS[m]
        df_month = datasets[m]

        for lead in range(2, 10):
            df_lead = df_month[df_month["lead_day"] == lead].copy()

            # Exact partition based on INITIALIZATION DATE
            train_df = df_lead[df_lead["init_time"] <= pd.Timestamp(splits["train_end"])].copy()
            calib_df = df_lead[
                (df_lead["init_time"] >= pd.Timestamp(splits["calib_start"])) &
                (df_lead["init_time"] <= pd.Timestamp(splits["calib_end"]))
            ].copy()
            test_df = df_lead[
                (df_lead["init_time"] >= pd.Timestamp(splits["test_start"])) &
                (df_lead["init_time"] <= pd.Timestamp(splits["test_end"]))
            ].copy()

            assert len(train_df) == 98100, f"Train count mismatch for {m} D{lead}: {len(train_df)}"
            assert len(calib_df) == 24525, f"Calib count mismatch for {m} D{lead}: {len(calib_df)}"
            assert len(test_df) == 24525, f"Test count mismatch for {m} D{lead}: {len(test_df)}"

            eval_res = evaluate_model_pipeline(
                train_df=train_df,
                calib_df=calib_df,
                test_df=test_df,
                context_label=f"{m.capitalize()} 2023 D{lead}",
            )
            # Remove raw prediction arrays from saved JSON
            eval_res.pop("_predictions", None)
            monthly_results[m][f"d{lead}"] = eval_res
            print(f"      {m.capitalize()} D{lead}: Baseline MAE={eval_res['regression']['baseline']['mae']:.2f}, "
                  f"XGB MAE={eval_res['regression']['overall_test']['mae']:.2f} "
                  f"(+{eval_res['regression']['overall_test']['mae_improvement_pct']}%), "
                  f"Cov={eval_res['conformal']['empirical_coverage_pct']:.1f}%, "
                  f"Rule B F1={eval_res['bust_detection']['rule_b']['metrics']['f1_score']:.3f}")

    # 4. Pooled D2–D9 Models (8 independent pooled lead models)
    print("\n[4/5] Training and Evaluating 8 Pooled Multi-Month Lead Models (Part 15)...")
    pooled_results = {}
    pooled_intensity_results = {}

    for lead in range(2, 10):
        # Assemble 3-month pooled datasets for this lead
        train_dfs, calib_dfs, test_dfs = [], [], []
        month_test_indices = {}
        current_idx = 0

        for m in ["july", "august", "september"]:
            df_lead = datasets[m][datasets[m]["lead_day"] == lead]
            splits = MONTH_SPLITS[m]

            tr = df_lead[df_lead["init_time"] <= pd.Timestamp(splits["train_end"])]
            ca = df_lead[
                (df_lead["init_time"] >= pd.Timestamp(splits["calib_start"])) &
                (df_lead["init_time"] <= pd.Timestamp(splits["calib_end"]))
            ]
            te = df_lead[
                (df_lead["init_time"] >= pd.Timestamp(splits["test_start"])) &
                (df_lead["init_time"] <= pd.Timestamp(splits["test_end"]))
            ]

            train_dfs.append(tr)
            calib_dfs.append(ca)
            test_dfs.append(te)

            month_test_indices[m] = (current_idx, current_idx + len(te))
            current_idx += len(te)

        pooled_train = pd.concat(train_dfs, ignore_index=True)
        pooled_calib = pd.concat(calib_dfs, ignore_index=True)
        pooled_test = pd.concat(test_dfs, ignore_index=True)

        assert len(pooled_train) == 294300, f"Pooled train count mismatch: {len(pooled_train)}"
        assert len(pooled_calib) == 73575, f"Pooled calib count mismatch: {len(pooled_calib)}"
        assert len(pooled_test) == 73575, f"Pooled test count mismatch: {len(pooled_test)}"

        eval_res = evaluate_model_pipeline(
            train_df=pooled_train,
            calib_df=pooled_calib,
            test_df=pooled_test,
            context_label=f"Pooled Multi-Month D{lead}",
        )

        preds = eval_res.pop("_predictions")
        baseline_med = eval_res["regression"]["baseline"]["median_error_mm"]

        # Evaluate individual monthly subsets under the pooled model
        subsets = {}
        for m in ["july", "august", "september"]:
            start_i, end_i = month_test_indices[m]
            subsets[f"{m}_test"] = evaluate_subset_predictions(
                y_test=preds["y_test"][start_i:end_i],
                raw_pred=preds["raw_pred"][start_i:end_i],
                cqr_lower=preds["cqr_lower"][start_i:end_i],
                cqr_upper=preds["cqr_upper"][start_i:end_i],
                f_apcp=preds["f_apcp"][start_i:end_i],
                is_bust_true=preds["is_bust_true"][start_i:end_i],
                baseline_median=baseline_med,
                context_label=f"Pooled D{lead} on {m.capitalize()} Test Subset",
            )

        eval_res["subsets"] = subsets
        pooled_results[f"d{lead}"] = eval_res

        # Rainfall Intensity Stratification (Part 14)
        strat = compute_intensity_stratification(
            o_rain=preds["o_rain"],
            y_test=preds["y_test"],
            raw_pred=preds["raw_pred"],
            is_bust_true=preds["is_bust_true"],
        )
        pooled_intensity_results[f"d{lead}"] = strat

        print(f"      Pooled D{lead}: Baseline MAE={eval_res['regression']['baseline']['mae']:.2f}, "
              f"XGB MAE={eval_res['regression']['overall_test']['mae']:.2f} "
              f"(+{eval_res['regression']['overall_test']['mae_improvement_pct']}%), "
              f"Cov={eval_res['conformal']['empirical_coverage_pct']:.1f}%, "
              f"Width={eval_res['conformal']['mean_interval_width']:.2f} mm, "
              f"Rule B F1={eval_res['bust_detection']['rule_b']['metrics']['f1_score']:.3f}")

    # 5. Build Authoritative D1–D9 Reliability Profile (Table F)
    print("\n[5/5] Synthesizing Complete D1–D9 Reliability Profile (Table F)...")
    profile = []

    # Lead 1: from authoritative Phase 1B pooled combined test
    p1b_comb = d1_authoritative["pooled"]["combined_test"]
    profile.append({
        "lead_day": 1,
        "lead_label": "D1 (+24h)",
        "baseline_mae": p1b_comb["regression"]["baseline"]["mae"],
        "xgb_mae": p1b_comb["regression"]["overall_test"]["mae"],
        "mae_improvement_pct": p1b_comb["regression"]["overall_test"]["mae_improvement_pct"],
        "baseline_rmse": p1b_comb["regression"]["baseline"]["rmse"],
        "xgb_rmse": p1b_comb["regression"]["overall_test"]["rmse"],
        "conformal_coverage_pct": p1b_comb["conformal"]["empirical_coverage_pct"],
        "mean_interval_width": p1b_comb["conformal"]["mean_interval_width"],
        "rule_a_f1": p1b_comb["bust_detection"]["rule_a"]["metrics"]["f1_score"],
        "rule_b_f1": p1b_comb["bust_detection"]["rule_b"]["metrics"]["f1_score"],
        "rule_c_f1": p1b_comb["bust_detection"]["rule_c"]["metrics"]["f1_score"],
        "test_bust_prevalence_pct": p1b_comb["sample_counts"]["test_bust_prevalence_pct"],
    })

    # Leads 2 through 9: from newly evaluated pooled models
    for lead in range(2, 10):
        res = pooled_results[f"d{lead}"]
        profile.append({
            "lead_day": lead,
            "lead_label": f"D{lead} (+{lead*24}h)",
            "baseline_mae": res["regression"]["baseline"]["mae"],
            "xgb_mae": res["regression"]["overall_test"]["mae"],
            "mae_improvement_pct": res["regression"]["overall_test"]["mae_improvement_pct"],
            "baseline_rmse": res["regression"]["baseline"]["rmse"],
            "xgb_rmse": res["regression"]["overall_test"]["rmse"],
            "conformal_coverage_pct": res["conformal"]["empirical_coverage_pct"],
            "mean_interval_width": res["conformal"]["mean_interval_width"],
            "rule_a_f1": res["bust_detection"]["rule_a"]["metrics"]["f1_score"],
            "rule_b_f1": res["bust_detection"]["rule_b"]["metrics"]["f1_score"],
            "rule_c_f1": res["bust_detection"]["rule_c"]["metrics"]["f1_score"],
            "test_bust_prevalence_pct": res["sample_counts"]["test_bust_prevalence_pct"],
        })

    # 6. Save Full Structured Output to JSON
    output_package = {
        "metadata": {
            "evaluation_title": "VISHWAS Phase 2A: Medium-Range Real-Data Validation (D1–D9)",
            "cycle": "00:00 UTC cycle, multi-lead accumulation differences (D1 through D9)",
            "nwp_source": "NOAA Global Forecast System (GFS) 0.25° Open Data AWS",
            "obs_source": "India Meteorological Department (IMD) 0.25° Gridded Daily Rainfall",
            "active_cells_per_day": 4905,
            "feature_columns": FEATURE_COLS,
            "target_column": TARGET_COL,
            "hyperparameters": XGB_PARAMS,
            "conformal_method": "Split Conformal Prediction (MAPIE SplitConformalRegressor)",
            "nominal_coverage_pct": 80.0,
            "bust_truth_formula": "ABS(F - O) > 25.0 mm AND (F > 10.0 mm OR O > 10.0 mm)",
            "d10_status": "UNAVAILABLE_EMPIRICALLY",
            "d10_boundary_explanation": (
                "D10 is not empirically validated in Phase 2A because the selected GFS 0.25° "
                "historical archive does not provide the +243h endpoint at the required 3-hour "
                "cadence needed to preserve the existing 03 UTC observation alignment."
            ),
            "fss_status": "DEFERRED",
            "fss_deferred_explanation": (
                "FSS is retained as a planned spatial-verification phase. The current empirical "
                "pipeline does not yet define the fixed neighborhood scale, precipitation threshold, "
                "and aggregation protocol required for a defensible FSS measurement."
            ),
        },
        "d1_authoritative_baseline": d1_authoritative,
        "monthly_models_d2_d9": monthly_results,
        "pooled_models_d2_d9": pooled_results,
        "rainfall_intensity_stratification": pooled_intensity_results,
        "d1_d9_reliability_profile": profile,
    }

    with open(metrics_out, "w", encoding="utf-8") as f:
        json.dump(output_package, f, indent=2)
    print(f"\nStructured validation metrics written to: {metrics_out}")

    # 7. Print Formatted Core Markdown Tables
    print_markdown_tables(monthly_results, pooled_results, profile, pooled_intensity_results, d1_authoritative)

    elapsed_total = time.time() - t_start
    print(f"Phase 2A Evaluation finished in {elapsed_total:.1f}s.")


def print_markdown_tables(monthly_results, pooled_results, profile, intensity_results, d1_auth):
    """Render all required Core Markdown Tables (Table B through Table G)."""
    # TABLE B: MONTH X LEAD REGRESSION
    print("\n### TABLE B — MONTH × LEAD REGRESSION")
    print("| Month | Lead | Baseline MAE | XGB MAE | MAE Improvement | Baseline RMSE | XGB RMSE |")
    print("|---|---|---|---|---|---|---|")
    for m in ["july", "august", "september"]:
        # D1 from authoritative
        d1_m = d1_auth["monthly"][m]["regression"]
        print(f"| {m.capitalize()} | D1 | {d1_m['baseline']['mae']:.2f} | {d1_m['overall_test']['mae']:.2f} | "
              f"{d1_m['overall_test']['mae_improvement_pct']:.2f}% | {d1_m['baseline']['rmse']:.2f} | {d1_m['overall_test']['rmse']:.2f} |")
        for lead in range(2, 10):
            res = monthly_results[m][f"d{lead}"]["regression"]
            print(f"| {m.capitalize()} | D{lead} | {res['baseline']['mae']:.2f} | {res['overall_test']['mae']:.2f} | "
                  f"{res['overall_test']['mae_improvement_pct']:.2f}% | {res['baseline']['rmse']:.2f} | {res['overall_test']['rmse']:.2f} |")

    # TABLE C: MONTH X LEAD CONFORMAL
    print("\n### TABLE C — MONTH × LEAD CONFORMAL")
    print("| Month | Lead | Nominal Coverage | Empirical Coverage | Mean Width | Median Width |")
    print("|---|---|---|---|---|---|")
    for m in ["july", "august", "september"]:
        d1_c = d1_auth["monthly"][m]["conformal"]
        print(f"| {m.capitalize()} | D1 | 80.0% | {d1_c['empirical_coverage_pct']:.1f}% | {d1_c['mean_interval_width']:.2f} mm | {d1_c['median_interval_width']:.2f} mm |")
        for lead in range(2, 10):
            res = monthly_results[m][f"d{lead}"]["conformal"]
            print(f"| {m.capitalize()} | D{lead} | 80.0% | {res['empirical_coverage_pct']:.1f}% | {res['mean_interval_width']:.2f} mm | {res['median_interval_width']:.2f} mm |")

    # TABLE D: MONTH X LEAD BUST DETECTION
    print("\n### TABLE D — MONTH × LEAD BUST DETECTION")
    print("| Month | Lead | Rule | Precision | Recall | F1 | Balanced Accuracy | MCC |")
    print("|---|---|---|---|---|---|---|---|")
    for m in ["july", "august", "september"]:
        # D1 rules
        d1_b = d1_auth["monthly"][m]["bust_detection"]
        for r_key, r_name in [("rule_a", "Rule A"), ("rule_b", "Rule B"), ("rule_c", "Rule C")]:
            met = d1_b[r_key]["metrics"]
            print(f"| {m.capitalize()} | D1 | {r_name} | {met['precision']:.3f} | {met['recall']:.3f} | {met['f1_score']:.3f} | {met['balanced_accuracy']:.3f} | {met['matthews_corrcoef']:.3f} |")
        for lead in range(2, 10):
            b_res = monthly_results[m][f"d{lead}"]["bust_detection"]
            for r_key, r_name in [("rule_a", "Rule A"), ("rule_b", "Rule B"), ("rule_c", "Rule C")]:
                met = b_res[r_key]["metrics"]
                print(f"| {m.capitalize()} | D{lead} | {r_name} | {met['precision']:.3f} | {met['recall']:.3f} | {met['f1_score']:.3f} | {met['balanced_accuracy']:.3f} | {met['matthews_corrcoef']:.3f} |")

    # TABLE E: POOLED LEAD PERFORMANCE
    print("\n### TABLE E — POOLED LEAD PERFORMANCE")
    print("| Lead | Test N | Baseline MAE | XGB MAE | XGB RMSE | Mean Bias | Coverage | Rule A F1 | Rule B F1 | Rule C F1 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    # D1
    p1b_comb = d1_auth["pooled"]["combined_test"]
    print(f"| D1 | {p1b_comb['sample_counts']['test']:,} | {p1b_comb['regression']['baseline']['mae']:.2f} | "
          f"{p1b_comb['regression']['overall_test']['mae']:.2f} | {p1b_comb['regression']['overall_test']['rmse']:.2f} | "
          f"{p1b_comb['regression']['overall_test']['mean_bias']:.2f} | {p1b_comb['conformal']['empirical_coverage_pct']:.1f}% | "
          f"{p1b_comb['bust_detection']['rule_a']['metrics']['f1_score']:.3f} | "
          f"{p1b_comb['bust_detection']['rule_b']['metrics']['f1_score']:.3f} | "
          f"{p1b_comb['bust_detection']['rule_c']['metrics']['f1_score']:.3f} |")
    for lead in range(2, 10):
        res = pooled_results[f"d{lead}"]
        print(f"| D{lead} | {res['sample_counts']['test']:,} | {res['regression']['baseline']['mae']:.2f} | "
              f"{res['regression']['overall_test']['mae']:.2f} | {res['regression']['overall_test']['rmse']:.2f} | "
              f"{res['regression']['overall_test']['mean_bias']:.2f} | {res['conformal']['empirical_coverage_pct']:.1f}% | "
              f"{res['bust_detection']['rule_a']['metrics']['f1_score']:.3f} | "
              f"{res['bust_detection']['rule_b']['metrics']['f1_score']:.3f} | "
              f"{res['bust_detection']['rule_c']['metrics']['f1_score']:.3f} |")

    # TABLE F: D1–D9 RELIABILITY PROFILE
    print("\n### TABLE F — D1–D9 RELIABILITY PROFILE")
    print("| Lead | Baseline MAE | XGB MAE | MAE Improvement | Baseline RMSE | XGB RMSE | Coverage | Mean Width | Rule A F1 | Rule B F1 | Rule C F1 | Bust Prev |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in profile:
        print(f"| {row['lead_label']} | {row['baseline_mae']:.2f} | {row['xgb_mae']:.2f} | {row['mae_improvement_pct']:.2f}% | "
              f"{row['baseline_rmse']:.2f} | {row['xgb_rmse']:.2f} | {row['conformal_coverage_pct']:.1f}% | "
              f"{row['mean_interval_width']:.2f} mm | {row['rule_a_f1']:.3f} | {row['rule_b_f1']:.3f} | {row['rule_c_f1']:.3f} | {row['test_bust_prevalence_pct']:.2f}% |")

    # TABLE G: INTENSITY STRATIFICATION
    print("\n### TABLE G — RAINFALL INTENSITY BEHAVIOR (POOLED TEST SET)")
    print("| Lead | Rainfall Bin | N | MAE | RMSE | Mean Bias | Bust Prevalence |")
    print("|---|---|---|---|---|---|---|")
    for lead in range(2, 10):
        lead_strat = intensity_results[f"d{lead}"]
        for b_name, b_data in lead_strat.items():
            print(f"| D{lead} | {b_name} | {b_data['sample_count']:,} | {b_data['mae']:.2f} | "
                  f"{b_data['rmse']:.2f} | {b_data['mean_bias']:.2f} | {b_data['bust_prevalence_pct']:.2f}% |")


if __name__ == "__main__":
    main()
