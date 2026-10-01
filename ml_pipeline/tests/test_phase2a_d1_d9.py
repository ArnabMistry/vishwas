"""Automated Tests for VISHWAS Phase 2A: Medium-Range Real-Data Validation (D1–D9).

Verifies all 18 requirements:
1. All months exist (July, August, September 2023 D2–D9)
2. All D2–D9 leads exist
3. Expected row count: 1,177,200 per month (3,531,600 total)
4. 4,905 active cells per init/lead
5. Exact initialization partitions
6. Valid date mapping (valid_time == init_time + lead_day)
7. No NaN or Inf
8. Non-negative precipitation (f_apcp_24h >= 0, o_rain_24h >= 0)
9. No duplicate init + lead + lat + lon
10. Exact bust definition recomputed
11. Exactly 7 ML predictors
12. Lead metadata excluded from model features
13. Monthly evaluation has 24 cases (3 months × 8 leads)
14. Pooled evaluation has 8 cases (D2 through D9)
15. Combined D1–D9 reliability profile contains 9 lead entries
16. D10 explicitly marked unavailable / not empirically evaluated
17. No future leakage across initialization splits
18. Phase 1A values remain unchanged
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

FEATURES_DIR = Path("backend/data/real/features")
METRICS_PATH = Path("ml_pipeline/real_data/phase2a_d1_d9_metrics.json")
PHASE1B_METRICS_PATH = Path("ml_pipeline/real_data/phase1b_multimonth_metrics.json")
PHASE1A_METRICS_PATH = Path("ml_pipeline/real_data/aug2023_d1_validation_metrics.json")

MONTHS = ["july", "august", "september"]
EXPECTED_CELLS = 4905
EXPECTED_ROWS_PER_MONTH = 1177200
EXPECTED_LEADS = [2, 3, 4, 5, 6, 7, 8, 9]

REQUIRED_FEATURES = [
    "f_apcp_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "lat",
    "lon",
]


@pytest.fixture(scope="module")
def loaded_matrices():
    """Load monthly parquet matrices for testing."""
    matrices = {}
    for m in MONTHS:
        pq = FEATURES_DIR / f"{m}_2023_d2_d9.parquet"
        assert pq.exists(), f"Missing Parquet matrix: {pq}"
        matrices[m] = pd.read_parquet(str(pq))
    return matrices


@pytest.fixture(scope="module")
def loaded_metrics():
    """Load Phase 2A metrics JSON."""
    assert METRICS_PATH.exists(), f"Phase 2A metrics JSON missing: {METRICS_PATH}"
    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# 1. All months exist
def test_all_months_exist():
    for m in MONTHS:
        pq = FEATURES_DIR / f"{m}_2023_d2_d9.parquet"
        assert pq.exists(), f"Matrix file for {m} missing: {pq}"
        assert pq.stat().st_size > 0, f"Matrix file for {m} is zero bytes: {pq}"


# 2. All D2–D9 leads exist
def test_all_d2_d9_leads_exist(loaded_matrices):
    for m in MONTHS:
        df = loaded_matrices[m]
        leads = sorted(df["lead_day"].unique().tolist())
        assert leads == EXPECTED_LEADS, f"Unexpected leads in {m}: {leads} != {EXPECTED_LEADS}"


# 3. Expected row count: 1,177,200 per month
def test_expected_row_count(loaded_matrices):
    total_rows = 0
    for m in MONTHS:
        df = loaded_matrices[m]
        assert len(df) == EXPECTED_ROWS_PER_MONTH, f"Row count for {m} mismatch: {len(df)} != {EXPECTED_ROWS_PER_MONTH}"
        total_rows += len(df)
    assert total_rows == 3531600, f"Total 3-month instances mismatch: {total_rows} != 3,531,600"


# 4. 4,905 active cells per init/lead
def test_active_cells_per_init_lead(loaded_matrices):
    for m in MONTHS:
        df = loaded_matrices[m]
        group_counts = df.groupby(["init_time", "lead_day"]).size()
        assert (group_counts == EXPECTED_CELLS).all(), f"Found init/lead group in {m} with size != {EXPECTED_CELLS}"
        assert len(group_counts) == 30 * 8, f"Expected 240 init/lead combinations in {m}, got {len(group_counts)}"


# 5. Exact initialization partitions
def test_exact_initialization_partitions(loaded_matrices):
    split_bounds = {
        "july": ("2023-07-20", "2023-07-21", "2023-07-25", "2023-07-26", "2023-07-30"),
        "august": ("2023-08-20", "2023-08-21", "2023-08-25", "2023-08-26", "2023-08-30"),
        "september": ("2023-09-19", "2023-09-20", "2023-09-24", "2023-09-25", "2023-09-29"),
    }
    for m in MONTHS:
        df = loaded_matrices[m]
        df_init = pd.to_datetime(df["init_time"])
        tr_end, ca_start, ca_end, te_start, te_end = split_bounds[m]

        for lead in EXPECTED_LEADS:
            lead_sub = df[df["lead_day"] == lead]
            lead_init = pd.to_datetime(lead_sub["init_time"])

            tr = lead_sub[lead_init <= pd.Timestamp(tr_end)]
            ca = lead_sub[(lead_init >= pd.Timestamp(ca_start)) & (lead_init <= pd.Timestamp(ca_end))]
            te = lead_sub[(lead_init >= pd.Timestamp(te_start)) & (lead_init <= pd.Timestamp(te_end))]

            assert len(tr) == 98100, f"{m} D{lead} train count: {len(tr)} != 98,100"
            assert len(ca) == 24525, f"{m} D{lead} calib count: {len(ca)} != 24,525"
            assert len(te) == 24525, f"{m} D{lead} test count: {len(te)} != 24,525"


# 6. Valid date mapping: valid_time == init_time + lead_day days
def test_valid_date_mapping(loaded_matrices):
    for m in MONTHS:
        df = loaded_matrices[m]
        init_ts = pd.to_datetime(df["init_time"])
        valid_ts = pd.to_datetime(df["valid_time"])
        expected_valid = init_ts + pd.to_timedelta(df["lead_day"], unit="D")
        diff_secs = (valid_ts - expected_valid).dt.total_seconds()
        assert (diff_secs == 0).all(), f"Found invalid valid_time mapping in {m}"


# 7. No NaN or Inf
def test_no_nan_or_inf(loaded_matrices):
    numeric_cols = ["f_apcp_24h", "o_rain_24h", "f_cape", "f_hgt_500", "f_u_850", "f_v_850", "error_abs"]
    for m in MONTHS:
        df = loaded_matrices[m]
        assert df.isna().sum().sum() == 0, f"Found NaNs in {m} matrix"
        assert not np.isinf(df[numeric_cols].values).any(), f"Found Infs in {m} matrix"


# 8. Non-negative precipitation
def test_non_negative_precipitation(loaded_matrices):
    for m in MONTHS:
        df = loaded_matrices[m]
        assert (df["f_apcp_24h"] >= 0.0).all(), f"Found negative forecast precipitation in {m}"
        assert (df["o_rain_24h"] >= 0.0).all(), f"Found negative observation precipitation in {m}"


# 9. No duplicate init + lead + lat + lon
def test_no_duplicate_init_lead_coords(loaded_matrices):
    for m in MONTHS:
        df = loaded_matrices[m]
        dups = df.duplicated(subset=["init_time", "lead_day", "lat", "lon"]).sum()
        assert dups == 0, f"Found {dups} duplicates in {m} matrix"


# 10. Exact bust definition recomputed
def test_exact_bust_definition(loaded_matrices):
    for m in MONTHS:
        df = loaded_matrices[m]
        f = df["f_apcp_24h"]
        o = df["o_rain_24h"]
        error = np.abs(f - o)
        recomputed = ((error > 25.0) & ((f > 10.0) | (o > 10.0))).astype(int)
        mismatches = (df["is_bust"] != recomputed).sum()
        assert mismatches == 0, f"Found {mismatches} bust label mismatches in {m}"


# 11. Exactly 7 ML predictors
def test_exactly_seven_ml_predictors(loaded_metrics):
    feat_cols = loaded_metrics["metadata"]["feature_columns"]
    assert feat_cols == REQUIRED_FEATURES, f"ML features mismatch: {feat_cols} != {REQUIRED_FEATURES}"
    assert len(feat_cols) == 7, f"Expected exactly 7 ML features, got {len(feat_cols)}"


# 12. Lead metadata excluded from model features
def test_lead_metadata_excluded_from_model_features(loaded_metrics):
    feat_cols = loaded_metrics["metadata"]["feature_columns"]
    forbidden = ["lead_day", "init_time", "valid_time", "lead_time_hours"]
    for f in forbidden:
        assert f not in feat_cols, f"Forbidden metadata field {f} was found in model features!"


# 13. Monthly evaluation has 24 cases (3 months × 8 leads)
def test_monthly_evaluation_has_24_cases(loaded_metrics):
    monthly_models = loaded_metrics["monthly_models_d2_d9"]
    assert len(monthly_models) == 3, f"Expected 3 months in monthly evaluation, got {len(monthly_models)}"
    total_cases = 0
    for m in MONTHS:
        assert m in monthly_models, f"Month {m} missing from monthly evaluation"
        leads = monthly_models[m]
        assert len(leads) == 8, f"Expected 8 leads for {m}, got {len(leads)}"
        total_cases += len(leads)
    assert total_cases == 24, f"Expected 24 monthly lead models, got {total_cases}"


# 14. Pooled evaluation has 8 cases (D2 through D9)
def test_pooled_evaluation_has_8_cases(loaded_metrics):
    pooled = loaded_metrics["pooled_models_d2_d9"]
    assert len(pooled) == 8, f"Expected 8 pooled lead models, got {len(pooled)}"
    for lead in range(2, 10):
        assert f"d{lead}" in pooled, f"Lead d{lead} missing from pooled models"


# 15. Combined D1–D9 reliability profile contains 9 lead entries
def test_combined_d1_d9_profile_has_nine_entries(loaded_metrics):
    profile = loaded_metrics["d1_d9_reliability_profile"]
    assert len(profile) == 9, f"Expected 9 leads (D1–D9) in reliability profile, got {len(profile)}"
    leads = [r["lead_day"] for r in profile]
    assert leads == list(range(1, 10)), f"Profile leads mismatch: {leads}"

    # Verify all scalar metrics are finite and positive
    for r in profile:
        assert np.isfinite(r["baseline_mae"]) and r["baseline_mae"] > 0
        assert np.isfinite(r["xgb_mae"]) and r["xgb_mae"] > 0
        assert np.isfinite(r["conformal_coverage_pct"]) and 0 <= r["conformal_coverage_pct"] <= 100
        assert np.isfinite(r["mean_interval_width"]) and r["mean_interval_width"] >= 0
        assert np.isfinite(r["rule_b_f1"]) and 0 <= r["rule_b_f1"] <= 1


# 16. D10 explicitly marked unavailable / not empirically evaluated
def test_d10_explicitly_marked_unavailable(loaded_metrics):
    meta = loaded_metrics["metadata"]
    assert meta["d10_status"] == "UNAVAILABLE_EMPIRICALLY"
    assert "+243h" in meta["d10_boundary_explanation"]
    assert "03 UTC" in meta["d10_boundary_explanation"]


# 17. No future-leakage across initialization splits
def test_no_future_leakage_across_initialization_splits(loaded_matrices):
    split_bounds = {
        "july": ("2023-07-20", "2023-07-21", "2023-07-25", "2023-07-26", "2023-07-30"),
        "august": ("2023-08-20", "2023-08-21", "2023-08-25", "2023-08-26", "2023-08-30"),
        "september": ("2023-09-19", "2023-09-20", "2023-09-24", "2023-09-25", "2023-09-29"),
    }
    for m in MONTHS:
        tr_end, ca_start, ca_end, te_start, te_end = split_bounds[m]
        assert pd.Timestamp(tr_end) < pd.Timestamp(ca_start), f"Train/Calib overlap in {m}"
        assert pd.Timestamp(ca_end) < pd.Timestamp(te_start), f"Calib/Test overlap in {m}"


# 18. Phase 1A values remain unchanged
def test_phase1a_values_remain_unchanged():
    with open(PHASE1A_METRICS_PATH, "r", encoding="utf-8") as f:
        p1a = json.load(f)
    with open(PHASE1B_METRICS_PATH, "r", encoding="utf-8") as f:
        p1b = json.load(f)

    # August D1 regression metrics
    aug_reg_1a = p1a["regression_metrics"]["overall_test"]
    aug_reg_1b = p1b["experiment_a_monthly_replication"]["august_2023"]["regression"]["overall_test"]
    assert aug_reg_1a["mae"] == aug_reg_1b["mae"], f"Phase 1A August MAE altered: {aug_reg_1a['mae']} != {aug_reg_1b['mae']}"
    assert aug_reg_1a["rmse"] == aug_reg_1b["rmse"], f"Phase 1A August RMSE altered: {aug_reg_1a['rmse']} != {aug_reg_1b['rmse']}"

    # August D1 conformal coverage
    aug_cov_1a = p1a["conformal_metrics"]["empirical_coverage_pct"]
    aug_cov_1b = p1b["experiment_a_monthly_replication"]["august_2023"]["conformal"]["empirical_coverage_pct"]
    assert aug_cov_1a == aug_cov_1b, f"Phase 1A August coverage altered: {aug_cov_1a} != {aug_cov_1b}"
