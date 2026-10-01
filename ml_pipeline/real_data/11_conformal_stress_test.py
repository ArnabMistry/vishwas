"""VISHWAS Phase 2B: Conformal Coverage Stress Test (Track A).

Scientific Scope:
- Objective: Diagnose empirical marginal coverage degradation from D1 through D9.
- Retrospective cohorts: July 2023, August 2023, September 2023.
- Models: 27 monthly models (3 months × 9 leads D1–D9) and 9 pooled multi-month models.
- Diagnostic components:
  1. Month × Lead Coverage, Shortfall (Coverage - 80%), Mean Width, Median Width.
  2. Calibration-to-Test Conformity-Score Diagnostics (Median, P80, P90, P95, Max).
  3. Rainfall-Conditioned Subgroup Coverage (0–10, 10–25, 25–50, 50–100, >100 mm).
  4. Descriptive Coverage Trend Classification (at or above, modestly below, materially below).

Outputs:
- ml_pipeline/real_data/phase2b_conformal_metrics.json
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from mapie.regression import SplitConformalRegressor

# Configure console output for Windows UTF-8 safety
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


def load_d1_to_d9_data(features_dir: Path) -> dict:
    """Load and unify D1 and D2–D9 datasets for July, August, September 2023."""
    datasets = {}
    for m in ["july", "august", "september"]:
        # D1 dataset
        d1_path = features_dir / f"{m}_2023_matrix.parquet"
        assert d1_path.exists(), f"Missing D1 matrix: {d1_path}"
        df_d1 = pd.read_parquet(str(d1_path))
        df_d1["valid_time"] = pd.to_datetime(df_d1["valid_time"])
        # For D1, init_time is valid_time minus 1 day (00:00 UTC cycle)
        df_d1["init_time"] = df_d1["valid_time"] - pd.Timedelta(days=1)
        df_d1["lead_day"] = 1
        df_d1["lead_time_hours"] = 24

        # D2-D9 dataset
        d2_d9_path = features_dir / f"{m}_2023_d2_d9.parquet"
        assert d2_d9_path.exists(), f"Missing D2-D9 matrix: {d2_d9_path}"
        df_d2_d9 = pd.read_parquet(str(d2_d9_path))
        df_d2_d9["init_time"] = pd.to_datetime(df_d2_d9["init_time"])
        df_d2_d9["valid_time"] = pd.to_datetime(df_d2_d9["valid_time"])

        # Concatenate D1 and D2-D9
        df_all = pd.concat([df_d1, df_d2_d9], ignore_index=True)
        datasets[m] = df_all
        print(f"Loaded {m.capitalize()}: {len(df_all):,} rows (Leads 1–9, {df_all['init_time'].nunique()} init dates)")
    return datasets


def evaluate_conformal_diagnostics(
    train_df: pd.DataFrame,
    calib_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> dict:
    """Fit model, calibrate Mapie SplitConformalRegressor, and extract exact distribution percentiles."""
    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL].values
    X_calib, y_calib = calib_df[FEATURE_COLS], calib_df[TARGET_COL].values
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL].values

    # 1. Fit XGBoost
    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X_train, y_train)

    # 2. Fit SplitConformalRegressor
    mapie = SplitConformalRegressor(estimator=model, confidence_level=0.80, prefit=True)
    mapie.conformalize(X_calib, y_calib)

    # Predictions
    calib_pred = model.predict(X_calib)
    test_pred, test_pis = mapie.predict_interval(X_test)

    cqr_lower = np.maximum(test_pis[:, 0, 0], 0.0)
    cqr_upper = test_pis[:, 1, 0]
    widths = cqr_upper - cqr_lower

    covered = (y_test >= cqr_lower) & (y_test <= cqr_upper)
    emp_coverage_pct = round(float(np.mean(covered) * 100.0), 2)
    mean_width = round(float(np.mean(widths)), 4)
    median_width = round(float(np.median(widths)), 4)
    shortfall = round(float(emp_coverage_pct - 80.0), 2)

    # Conformity scores on calibration: R_calib = |y_calib - y_hat_calib|
    calib_residuals = np.abs(y_calib - calib_pred)
    calib_dist = {
        "median": round(float(np.median(calib_residuals)), 4),
        "p80": round(float(np.percentile(calib_residuals, 80)), 4),
        "p90": round(float(np.percentile(calib_residuals, 90)), 4),
        "p95": round(float(np.percentile(calib_residuals, 95)), 4),
        "max": round(float(np.max(calib_residuals)), 4),
    }

    # Absolute errors on test: E_test = |y_test - y_hat_test|
    test_residuals = np.abs(y_test - test_pred)
    test_dist = {
        "median": round(float(np.median(test_residuals)), 4),
        "p80": round(float(np.percentile(test_residuals, 80)), 4),
        "p90": round(float(np.percentile(test_residuals, 90)), 4),
        "p95": round(float(np.percentile(test_residuals, 95)), 4),
        "max": round(float(np.max(test_residuals)), 4),
    }

    return {
        "empirical_coverage_pct": emp_coverage_pct,
        "coverage_shortfall_pct": shortfall,
        "mean_interval_width": mean_width,
        "median_interval_width": median_width,
        "calib_conformity_scores": calib_dist,
        "test_error_scores": test_dist,
        "_covered": covered,
        "_widths": widths,
        "_o_rain": test_df["o_rain_24h"].values,
    }


def classify_coverage_trend(cov_pct: float) -> str:
    """Classify coverage into descriptive reporting bins."""
    if cov_pct >= 80.0:
        return "at or above nominal"
    elif cov_pct >= 75.0:
        return "modestly below nominal"
    else:
        return "materially below nominal"


def main():
    t0 = time.time()
    features_dir = Path("backend/data/real/features")
    metrics_out = Path("ml_pipeline/real_data/phase2b_conformal_metrics.json")

    print("\n" + "=" * 75)
    print("VISHWAS PHASE 2B: CONFORMAL COVERAGE STRESS TEST (TRACK A)")
    print("=" * 75)

    # 1. Load Data
    datasets = load_d1_to_d9_data(features_dir)

    # 2. Month × Lead Evaluation (27 models)
    print("\n[1/3] Evaluating 27 Monthly Lead Models (3 Months × 9 Leads D1–D9)...")
    monthly_table_a = []
    monthly_results = {"july": {}, "august": {}, "september": {}}

    for m in ["july", "august", "september"]:
        splits = MONTH_SPLITS[m]
        df_m = datasets[m]
        m_title = m.capitalize() + " 2023"

        for lead in range(1, 10):
            df_lead = df_m[df_m["lead_day"] == lead].copy()

            tr = df_lead[df_lead["init_time"] <= pd.Timestamp(splits["train_end"])].copy()
            ca = df_lead[
                (df_lead["init_time"] >= pd.Timestamp(splits["calib_start"])) &
                (df_lead["init_time"] <= pd.Timestamp(splits["calib_end"]))
            ].copy()
            te = df_lead[
                (df_lead["init_time"] >= pd.Timestamp(splits["test_start"])) &
                (df_lead["init_time"] <= pd.Timestamp(splits["test_end"]))
            ].copy()

            assert len(tr) == 98100, f"Train row count error: {len(tr)}"
            assert len(ca) == 24525, f"Calib row count error: {len(ca)}"
            assert len(te) == 24525, f"Test row count error: {len(te)}"

            res = evaluate_conformal_diagnostics(tr, ca, te)
            res.pop("_covered", None)
            res.pop("_widths", None)
            res.pop("_o_rain", None)

            monthly_results[m][f"d{lead}"] = res
            monthly_table_a.append({
                "month": m_title,
                "lead": f"D{lead}",
                "coverage_pct": res["empirical_coverage_pct"],
                "shortfall_pct": res["coverage_shortfall_pct"],
                "mean_width": res["mean_interval_width"],
                "median_width": res["median_interval_width"],
            })

    print(f"      Evaluated 27 monthly models successfully.")

    # 3. Pooled Lead Models (9 models D1–D9)
    print("\n[2/3] Evaluating 9 Pooled Multi-Month Models (D1 through D9)...")
    pooled_results = {}
    table_b_conformity = []
    table_c_rainfall = []
    coverage_trend_summary = []

    for lead in range(1, 10):
        train_dfs, calib_dfs, test_dfs = [], [], []

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

        p_train = pd.concat(train_dfs, ignore_index=True)
        p_calib = pd.concat(calib_dfs, ignore_index=True)
        p_test = pd.concat(test_dfs, ignore_index=True)

        assert len(p_train) == 294300
        assert len(p_calib) == 73575
        assert len(p_test) == 73575

        res = evaluate_conformal_diagnostics(p_train, p_calib, p_test)

        cov_val = res["empirical_coverage_pct"]
        classification = classify_coverage_trend(cov_val)
        coverage_trend_summary.append({
            "lead": f"D{lead}",
            "coverage_pct": cov_val,
            "shortfall_pct": res["coverage_shortfall_pct"],
            "classification": classification,
        })

        # Table B: Calibration-to-Test Conformity Diagnostics
        c_dist = res["calib_conformity_scores"]
        t_dist = res["test_error_scores"]
        table_b_conformity.append({
            "lead": f"D{lead}",
            "calib_median": c_dist["median"],
            "calib_p80": c_dist["p80"],
            "calib_p90": c_dist["p90"],
            "calib_p95": c_dist["p95"],
            "calib_max": c_dist["max"],
            "test_median": t_dist["median"],
            "test_p80": t_dist["p80"],
            "test_p90": t_dist["p90"],
            "test_p95": t_dist["p95"],
            "test_max": t_dist["max"],
        })

        # Table C: Rainfall-Conditioned Subgroup Coverage
        covered = res.pop("_covered")
        widths = res.pop("_widths")
        o_rain = res.pop("_o_rain")

        subgroup_dict = {}
        for b_name, b_filter in RAIN_BINS:
            mask = b_filter(o_rain)
            n_sub = int(np.sum(mask))
            if n_sub > 0:
                sub_cov = round(float(np.mean(covered[mask]) * 100.0), 2)
                sub_mw = round(float(np.mean(widths[mask])), 4)
            else:
                sub_cov = 0.0
                sub_mw = 0.0

            subgroup_dict[b_name] = {
                "n_samples": n_sub,
                "coverage_pct": sub_cov,
                "mean_interval_width": sub_mw,
            }
            table_c_rainfall.append({
                "lead": f"D{lead}",
                "rainfall_bin": b_name,
                "n_samples": n_sub,
                "coverage_pct": sub_cov,
                "mean_width": sub_mw,
            })

        res["rainfall_conditioned_coverage"] = subgroup_dict
        pooled_results[f"d{lead}"] = res

        print(f"      D{lead}: Cov={cov_val:.2f}% ({classification}), Width={res['mean_interval_width']:.2f} mm | "
              f"Calib P80={c_dist['p80']:.2f}, Test P80={t_dist['p80']:.2f}")

    # 4. Save JSON Package
    print("\n[3/3] Writing Structured Stress-Test Metrics to JSON...")
    output_package = {
        "metadata": {
            "title": "VISHWAS Phase 2B: Conformal Coverage Stress Test (Track A)",
            "nominal_coverage_pct": 80.0,
            "leads_evaluated": [f"D{l}" for l in range(1, 10)],
            "methodology": "Split Conformal Prediction (MAPIE SplitConformalRegressor)",
            "classification_bins": {
                "at_or_above_nominal": ">= 80.0%",
                "modestly_below_nominal": "75.0% - 79.99%",
                "materially_below_nominal": "< 75.0%",
            },
            "disclaimer": (
                "This is a diagnostic study examining calibration-to-test distribution properties. "
                "Causality is not established. Subgroup statistics are diagnostic only."
            ),
        },
        "monthly_table_a_coverage": monthly_table_a,
        "pooled_table_b_conformity_diagnostics": table_b_conformity,
        "pooled_table_c_rainfall_coverage": table_c_rainfall,
        "pooled_coverage_trend_summary": coverage_trend_summary,
        "monthly_models": monthly_results,
        "pooled_models": pooled_results,
    }

    with open(metrics_out, "w", encoding="utf-8") as f:
        json.dump(output_package, f, indent=2)

    elapsed = time.time() - t0
    print(f"Conformal stress test finished in {elapsed:.1f}s. Saved to: {metrics_out}\n")


if __name__ == "__main__":
    main()
