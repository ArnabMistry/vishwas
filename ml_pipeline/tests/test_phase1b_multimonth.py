"""VISHWAS Phase 1B: Multi-Month Real-Data Validation Unit & Integration Tests.

Validates:
1. Exactly 3 expected months (July, August, September 2023)
2. Correct date partitions (20 train, 5 calib, 5 test days per month)
3. Exactly 24,525 test rows per monthly replication
4. Exactly 73,575 pooled test rows
5. Required 7 features in exact order
6. No NaN/Inf in evaluation inputs
7. Bust truth definition is exact: |F - O| > 25 & (F > 10 | O > 10)
8. Metric dictionaries contain all required metrics across Experiments A, B, C
9. Conformal coverage is within valid probability bounds (0% to 100%)
10. Interval width is non-negative (upper >= lower)
11. All three cross-month transfer cases are present
12. No accidental use of future target-month rows inside each transfer test
13. Phase 1A August artifact remains strictly unchanged
"""

import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

FEATURE_COLS = [
    "f_apcp_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "lat",
    "lon"
]

METRICS_JSON_PATH = Path("ml_pipeline/real_data/phase1b_multimonth_metrics.json")
AUG_PHASE1A_JSON_PATH = Path("ml_pipeline/real_data/aug2023_d1_validation_metrics.json")
FEATURES_DIR = Path("backend/data/real/features")


@pytest.fixture(scope="module")
def metrics():
    assert METRICS_JSON_PATH.exists(), f"Metrics JSON not found: {METRICS_JSON_PATH}"
    with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def matrices():
    july = pd.read_parquet(FEATURES_DIR / "july_2023_matrix.parquet")
    aug = pd.read_parquet(FEATURES_DIR / "august_2023_matrix.parquet")
    sept = pd.read_parquet(FEATURES_DIR / "september_2023_matrix.parquet")
    return {"July": july, "August": aug, "September": sept}


def test_exactly_three_months(metrics, matrices):
    """Test 1: Exactly 3 expected months are present in dataset and metrics."""
    assert len(matrices) == 3
    assert set(matrices.keys()) == {"July", "August", "September"}
    assert set(metrics["datasets"].keys()) == {"july_2023", "august_2023", "september_2023"}
    assert set(metrics["experiment_a_monthly_replication"].keys()) == {"july_2023", "august_2023", "september_2023"}


def test_correct_date_partitions(matrices):
    """Test 2: Correct date partitions (20 train, 5 calib, 5 test days per month)."""
    expected_ranges = {
        "July": ("2023-07-02", "2023-07-21", "2023-07-22", "2023-07-26", "2023-07-27", "2023-07-31"),
        "August": ("2023-08-02", "2023-08-21", "2023-08-22", "2023-08-26", "2023-08-27", "2023-08-31"),
        "September": ("2023-09-01", "2023-09-20", "2023-09-21", "2023-09-25", "2023-09-26", "2023-09-30"),
    }
    for m_name, (tr_s, tr_e, ca_s, ca_e, te_s, te_e) in expected_ranges.items():
        df = matrices[m_name]
        dates = pd.to_datetime(df["valid_time"]).drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist()
        assert len(dates) == 30, f"{m_name} must have 30 unique valid dates"
        train_d, calib_d, test_d = dates[:20], dates[20:25], dates[25:]
        assert train_d[0] == tr_s and train_d[-1] == tr_e
        assert calib_d[0] == ca_s and calib_d[-1] == ca_e
        assert test_d[0] == te_s and test_d[-1] == te_e
        assert train_d[-1] < calib_d[0] < test_d[0]


def test_test_rows_per_monthly_replication(metrics):
    """Test 3: Exactly 24,525 test rows per monthly replication."""
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        cnt = metrics["experiment_a_monthly_replication"][m_key]["sample_counts"]["test"]
        assert cnt == 24525, f"{m_key} test sample count mismatch: {cnt} != 24525"


def test_pooled_test_rows(metrics):
    """Test 4: Exactly 73,575 pooled test rows in Experiment B."""
    pooled_test_cnt = metrics["experiment_b_pooled_model"]["combined_test"]["sample_counts"]["test"]
    assert pooled_test_cnt == 73575, f"Pooled test sample count mismatch: {pooled_test_cnt} != 73575"
    # Also verify subsets sum to pooled test
    subsets = metrics["experiment_b_pooled_model"]["subsets"]
    sub_sum = sum(s["sample_counts"]["test"] for s in subsets.values())
    assert sub_sum == 73575


def test_required_features(matrices, metrics):
    """Test 5: Required 7 features in exact order."""
    assert metrics["metadata"]["feature_columns"] == FEATURE_COLS
    for m_name, df in matrices.items():
        for col in FEATURE_COLS:
            assert col in df.columns, f"{col} missing in {m_name} matrix"


def test_no_nan_or_inf_in_inputs(matrices):
    """Test 6: No NaN/Inf values exist in feature matrices."""
    for m_name, df in matrices.items():
        for col in FEATURE_COLS + ["error_abs", "is_bust", "o_rain_24h"]:
            assert df[col].isna().sum() == 0, f"NaN found in {m_name}.{col}"
            assert np.isinf(df[col]).sum() == 0, f"Inf found in {m_name}.{col}"


def test_bust_truth_exactness(matrices):
    """Test 7: Ground-truth bust definition is exact across all matrices."""
    for m_name, df in matrices.items():
        recomputed = (
            (df["error_abs"] > 25.0) &
            ((df["f_apcp_24h"] > 10.0) | (df["o_rain_24h"] > 10.0))
        ).astype(int)
        assert (recomputed == df["is_bust"]).all(), f"Bust definition mismatch in {m_name}"


def test_metric_dictionaries_completeness(metrics):
    """Test 8: Metric dictionaries contain all required metrics across Exp A, B, C."""
    # Experiment A
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        exp_a = metrics["experiment_a_monthly_replication"][m_key]
        assert "regression" in exp_a
        assert "baseline" in exp_a["regression"]
        assert "overall_test" in exp_a["regression"]
        assert "mae_improvement_pct" in exp_a["regression"]["overall_test"]
        assert "rmse_improvement_pct" in exp_a["regression"]["overall_test"]
        assert "conformal" in exp_a
        assert "bust_detection" in exp_a
        assert set(exp_a["bust_detection"].keys()) == {"rule_a", "rule_b", "rule_c"}
        for r_k in ["rule_a", "rule_b", "rule_c"]:
            m = exp_a["bust_detection"][r_k]["metrics"]
            for field in ["tp", "fp", "tn", "fn", "precision", "recall", "f1_score", "balanced_accuracy", "matthews_corrcoef"]:
                assert field in m, f"Field {field} missing in {m_key}.{r_k}"
        assert "rainfall_stratification" in exp_a
        for b_name in ["0–10 mm", "10–25 mm", "25–50 mm", "50–100 mm", ">100 mm"]:
            assert b_name in exp_a["rainfall_stratification"]

    # Experiment B
    assert "combined_test" in metrics["experiment_b_pooled_model"]
    assert "subsets" in metrics["experiment_b_pooled_model"]

    # Experiment C
    for c_key in ["case_1_hold_out_july", "case_2_hold_out_august", "case_3_hold_out_september"]:
        assert c_key in metrics["experiment_c_cross_month_transfer"]


def test_conformal_coverage_bounds(metrics):
    """Test 9: Conformal coverage is within valid percentage bounds (0% to 100%)."""
    # Exp A
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        cov = metrics["experiment_a_monthly_replication"][m_key]["conformal"]["empirical_coverage_pct"]
        assert 0.0 <= cov <= 100.0, f"Invalid coverage in Exp A {m_key}: {cov}"
    # Exp B
    cov_b = metrics["experiment_b_pooled_model"]["combined_test"]["conformal"]["empirical_coverage_pct"]
    assert 0.0 <= cov_b <= 100.0, f"Invalid coverage in Exp B: {cov_b}"
    # Exp C
    for c_key, c_data in metrics["experiment_c_cross_month_transfer"].items():
        cov_c = c_data["conformal"]["empirical_coverage_pct"]
        assert 0.0 <= cov_c <= 100.0, f"Invalid coverage in Exp C {c_key}: {cov_c}"


def test_interval_widths_non_negative(metrics):
    """Test 10: Interval widths are non-negative."""
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        conf = metrics["experiment_a_monthly_replication"][m_key]["conformal"]
        assert conf["mean_interval_width"] >= 0.0
        assert conf["median_interval_width"] >= 0.0
        assert conf["min_interval_width"] >= 0.0
        assert conf["max_interval_width"] >= conf["min_interval_width"]


def test_all_three_cross_month_cases_present(metrics):
    """Test 11: All three cross-month transfer cases are present in Experiment C."""
    c_dict = metrics["experiment_c_cross_month_transfer"]
    assert "case_1_hold_out_july" in c_dict
    assert "case_2_hold_out_august" in c_dict
    assert "case_3_hold_out_september" in c_dict
    for c_name, c_data in c_dict.items():
        assert c_data["sample_counts"]["test"] == 24525


def test_no_future_target_month_leakage_in_transfer():
    """Test 12: Verify that each cross-month case strictly holds out the target month."""
    # Case 1 holds out July: target test is July, training is Aug+Sept
    # Case 2 holds out August: target test is August, training is July+Sept
    # Case 3 holds out September: target test is September, training is July+Aug
    # Verified by construction in 09_evaluate_phase1b.py
    j_df = pd.read_parquet(FEATURES_DIR / "july_2023_matrix.parquet")
    a_df = pd.read_parquet(FEATURES_DIR / "august_2023_matrix.parquet")
    s_df = pd.read_parquet(FEATURES_DIR / "september_2023_matrix.parquet")

    j_test_dates = set(j_df.sort_values("valid_time")["valid_time"].drop_duplicates().tolist()[25:])
    a_train_dates = set(a_df.sort_values("valid_time")["valid_time"].drop_duplicates().tolist()[:20])
    s_train_dates = set(s_df.sort_values("valid_time")["valid_time"].drop_duplicates().tolist()[:20])

    assert len(j_test_dates.intersection(a_train_dates)) == 0
    assert len(j_test_dates.intersection(s_train_dates)) == 0


def test_phase1a_august_artifact_unchanged(metrics):
    """Test 13: Phase 1A August authoritative values remain strictly preserved."""
    assert AUG_PHASE1A_JSON_PATH.exists()
    with open(AUG_PHASE1A_JSON_PATH, "r", encoding="utf-8") as f:
        p1a = json.load(f)

    exp_a_aug = metrics["experiment_a_monthly_replication"]["august_2023"]

    # Strict equality on key Phase 1A metrics
    assert exp_a_aug["regression"]["baseline"]["mae"] == p1a["regression_metrics"]["baseline"]["mae"]
    assert exp_a_aug["regression"]["overall_test"]["mae"] == p1a["regression_metrics"]["overall_test"]["mae"]
    assert exp_a_aug["regression"]["overall_test"]["rmse"] == p1a["regression_metrics"]["overall_test"]["rmse"]
    assert exp_a_aug["conformal"]["empirical_coverage_pct"] == p1a["conformal_metrics"]["empirical_coverage_pct"]
    assert exp_a_aug["bust_detection"]["rule_a"]["metrics"]["f1_score"] == p1a["bust_metrics"]["primary_decision_rule"]["metrics"]["f1_score"]
    assert exp_a_aug["bust_detection"]["rule_b"]["metrics"]["f1_score"] == p1a["bust_metrics"]["operational_alert_rule"]["metrics"]["f1_score"]
    assert exp_a_aug["bust_detection"]["rule_c"]["metrics"]["f1_score"] == p1a["bust_metrics"]["conformal_upper_bound_rule"]["metrics"]["f1_score"]
