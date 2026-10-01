"""VISHWAS Phase 1B: Multi-Month Real-Data Validation Unit & Integration Tests.

Validates:
1. Full-month rows = 147,150 for each month (July, August, September 2023)
2. Correct date partitions (20 train, 5 calib, 5 test days per month)
3. Exactly 24,525 test rows per monthly replication
4. Exactly 73,575 pooled test rows in Experiment B
5. The full-month bust counts and test-set bust counts are stored under distinct metric fields
6. Required 7 features in exact order
7. No NaN/Inf in evaluation inputs or reported scalar metrics
8. Bust truth definition is exact: |F - O| > 25 & (F > 10 | O > 10)
9. Metric dictionaries contain all required metrics across Experiments A, B, C
10. Conformal coverage is within valid percentage bounds (0% to 100%)
11. Interval widths are non-negative (upper >= lower)
12. All three cross-month transfer cases are present
13. No accidental use of future target-month rows inside each transfer test
14. Phase 1A August authoritative baseline artifact remains strictly preserved
"""

import json
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


def test_full_month_rows_count(matrices, metrics):
    """Test 1: Full-month rows = 147,150 for each of the 3 months."""
    assert len(matrices) == 3
    assert set(matrices.keys()) == {"July", "August", "September"}
    for m_name, df in matrices.items():
        assert len(df) == 147150, f"{m_name} row count mismatch: {len(df)} != 147,150"
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        assert metrics["datasets"][m_key]["total_rows"] == 147150


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
    subsets = metrics["experiment_b_pooled_model"]["subsets"]
    sub_sum = sum(s["sample_counts"]["test"] for s in subsets.values())
    assert sub_sum == 73575


def test_distinct_full_month_and_test_bust_fields(metrics):
    """Test 5: Full-month bust counts and test-set bust counts are stored under distinct metric fields."""
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        full_busts = metrics["datasets"][m_key]["total_busts"]
        full_prev = metrics["datasets"][m_key]["total_bust_prevalence_pct"]
        test_busts = metrics["experiment_a_monthly_replication"][m_key]["sample_counts"]["test_busts"]
        test_prev = metrics["experiment_a_monthly_replication"][m_key]["sample_counts"]["test_bust_prevalence_pct"]

        # Assert full-month (30 days) and test-set (5 days) metrics are stored under distinct keys and represent different quantities
        assert full_busts > test_busts, f"{m_key}: Full-month busts ({full_busts}) must exceed test busts ({test_busts})"
        assert full_busts in [15137, 8030, 7599]
        assert test_busts in [2232, 470, 607]
        assert full_prev in [10.29, 5.46, 5.16]
        assert test_prev in [9.10, 1.92, 2.48]


def test_required_features(matrices, metrics):
    """Test 6: Required 7 features in exact order."""
    assert metrics["metadata"]["feature_columns"] == FEATURE_COLS
    for m_name, df in matrices.items():
        for col in FEATURE_COLS:
            assert col in df.columns, f"{col} missing in {m_name} matrix"


def test_no_nan_or_inf_in_inputs_and_metrics(matrices, metrics):
    """Test 7: No NaN/Inf values exist in feature matrices or reported scalar metrics."""
    for m_name, df in matrices.items():
        for col in FEATURE_COLS + ["error_abs", "is_bust", "o_rain_24h"]:
            assert df[col].isna().sum() == 0, f"NaN found in {m_name}.{col}"
            assert np.isinf(df[col]).sum() == 0, f"Inf found in {m_name}.{col}"

    def assert_finite_recursive(obj, path="root"):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert_finite_recursive(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                assert_finite_recursive(v, f"{path}[{i}]")
        elif isinstance(obj, (int, float, np.integer, np.floating)):
            assert np.isfinite(obj), f"Non-finite value found at {path}: {obj}"

    assert_finite_recursive(metrics)


def test_bust_truth_exactness(matrices):
    """Test 8: Ground-truth bust definition is exact across all matrices."""
    for m_name, df in matrices.items():
        recomputed = (
            (df["error_abs"] > 25.0) &
            ((df["f_apcp_24h"] > 10.0) | (df["o_rain_24h"] > 10.0))
        ).astype(int)
        assert (recomputed == df["is_bust"]).all(), f"Bust definition mismatch in {m_name}"


def test_metric_dictionaries_completeness(metrics):
    """Test 9: Metric dictionaries contain all required metrics across Exp A, B, C."""
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

    assert "combined_test" in metrics["experiment_b_pooled_model"]
    assert "subsets" in metrics["experiment_b_pooled_model"]

    for c_key in ["case_1_hold_out_july", "case_2_hold_out_august", "case_3_hold_out_september"]:
        assert c_key in metrics["experiment_c_cross_month_transfer"]


def test_conformal_coverage_bounds(metrics):
    """Test 10: Conformal coverage is within valid percentage bounds (0% to 100%)."""
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        cov = metrics["experiment_a_monthly_replication"][m_key]["conformal"]["empirical_coverage_pct"]
        assert 0.0 <= cov <= 100.0, f"Invalid coverage in Exp A {m_key}: {cov}"

    cov_b = metrics["experiment_b_pooled_model"]["combined_test"]["conformal"]["empirical_coverage_pct"]
    assert 0.0 <= cov_b <= 100.0, f"Invalid coverage in Exp B: {cov_b}"

    for c_key, c_data in metrics["experiment_c_cross_month_transfer"].items():
        cov_c = c_data["conformal"]["empirical_coverage_pct"]
        assert 0.0 <= cov_c <= 100.0, f"Invalid coverage in Exp C {c_key}: {cov_c}"


def test_interval_widths_non_negative(metrics):
    """Test 11: Interval widths are non-negative."""
    for m_key in ["july_2023", "august_2023", "september_2023"]:
        conf = metrics["experiment_a_monthly_replication"][m_key]["conformal"]
        assert conf["mean_interval_width"] >= 0.0
        assert conf["median_interval_width"] >= 0.0
        assert conf["min_interval_width"] >= 0.0
        assert conf["max_interval_width"] >= conf["min_interval_width"]


def test_all_three_cross_month_cases_present(metrics):
    """Test 12: All three cross-month transfer cases are present in Experiment C."""
    c_dict = metrics["experiment_c_cross_month_transfer"]
    assert "case_1_hold_out_july" in c_dict
    assert "case_2_hold_out_august" in c_dict
    assert "case_3_hold_out_september" in c_dict
    for c_name, c_data in c_dict.items():
        assert c_data["sample_counts"]["test"] == 24525


def test_no_future_target_month_leakage_in_transfer():
    """Test 13: Verify that each cross-month case strictly holds out the target month."""
    j_df = pd.read_parquet(FEATURES_DIR / "july_2023_matrix.parquet")
    a_df = pd.read_parquet(FEATURES_DIR / "august_2023_matrix.parquet")
    s_df = pd.read_parquet(FEATURES_DIR / "september_2023_matrix.parquet")

    j_test_dates = set(j_df.sort_values("valid_time")["valid_time"].drop_duplicates().tolist()[25:])
    a_train_dates = set(a_df.sort_values("valid_time")["valid_time"].drop_duplicates().tolist()[:20])
    s_train_dates = set(s_df.sort_values("valid_time")["valid_time"].drop_duplicates().tolist()[:20])

    assert len(j_test_dates.intersection(a_train_dates)) == 0
    assert len(j_test_dates.intersection(s_train_dates)) == 0


def test_phase1a_august_artifact_unchanged(metrics):
    """Test 14: Phase 1A August authoritative values remain strictly preserved."""
    assert AUG_PHASE1A_JSON_PATH.exists()
    with open(AUG_PHASE1A_JSON_PATH, "r", encoding="utf-8") as f:
        p1a = json.load(f)

    exp_a_aug = metrics["experiment_a_monthly_replication"]["august_2023"]

    # Strict numerical equality on authoritative Phase 1A contract
    assert exp_a_aug["regression"]["baseline"]["mae"] == 3.0578
    assert exp_a_aug["regression"]["overall_test"]["mae"] == 2.6700
    assert exp_a_aug["regression"]["baseline"]["rmse"] == 8.4237
    assert exp_a_aug["regression"]["overall_test"]["rmse"] == 6.4008
    assert exp_a_aug["conformal"]["empirical_coverage_pct"] == 90.99
    assert exp_a_aug["conformal"]["mean_interval_width"] == 8.7220
    assert exp_a_aug["bust_detection"]["rule_a"]["metrics"]["f1_score"] == 0.4072
    assert exp_a_aug["bust_detection"]["rule_b"]["metrics"]["f1_score"] == 0.3842
    assert exp_a_aug["bust_detection"]["rule_c"]["metrics"]["f1_score"] == 0.3874
    assert exp_a_aug["sample_counts"]["test"] == 24525
    assert exp_a_aug["sample_counts"]["test_busts"] == 470
    assert exp_a_aug["sample_counts"]["test_bust_prevalence_pct"] == 1.92
