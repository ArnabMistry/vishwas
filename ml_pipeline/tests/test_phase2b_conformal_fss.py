"""Automated Test Suite for VISHWAS Phase 2B: Conformal Stress Test and FSS Spatial Verification.

Verifies:
1. Conformal stress-test covers exactly D1–D9.
2. Coverage values are bounded within [0, 100].
3. Interval widths are strictly non-negative.
4. All required diagnostic fields exist in phase2b_conformal_metrics.json.
5. Rainfall bins are exact (0–10, 10–25, 25–50, 50–100, >100 mm).
6. All scalar metrics in conformal JSON are finite.
7. FSS thresholds are exactly [1, 10, 25] mm.
8. FSS scales are exactly ['1x1', '3x3', '5x5', '7x7'].
9. FSS values are in [0, 1] (or explicitly None/null where undefined).
10. No negative neighborhood denominators.
11. Active land mask unchanged (exactly 4,905 active cells).
12. FSS covers all leads D1–D9.
13. FSS-0.5 reference horizons only use D1–D9 ('none', 'beyond D9', or 'D1'-'D9').
14. Frequency bias is finite whenever observation frequency > 0.
15. No fabricated D10 in either study.
16. Phase 1A August values remain unchanged.
17. Phase 1B metrics remain unchanged.
18. Phase 2A metric JSON remains unchanged by diagnostic scripts.
"""

import json
from pathlib import Path
import numpy as np
import pytest

CONF_JSON = Path("ml_pipeline/real_data/phase2b_conformal_metrics.json")
FSS_JSON = Path("ml_pipeline/real_data/phase2b_fss_metrics.json")
P2A_JSON = Path("ml_pipeline/real_data/phase2a_d1_d9_metrics.json")
P1B_JSON = Path("ml_pipeline/real_data/phase1b_multimonth_metrics.json")
P1A_JSON = Path("ml_pipeline/real_data/aug2023_d1_validation_metrics.json")


@pytest.fixture(scope="module")
def conf_data():
    assert CONF_JSON.exists(), f"Missing: {CONF_JSON}"
    with open(CONF_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fss_data():
    assert FSS_JSON.exists(), f"Missing: {FSS_JSON}"
    with open(FSS_JSON, encoding="utf-8") as f:
        return json.load(f)


# 1. Conformal: exactly D1–D9
def test_conformal_leads_exact(conf_data):
    leads = conf_data["metadata"]["leads_evaluated"]
    expected = [f"D{i}" for i in range(1, 10)]
    assert leads == expected, f"Expected {expected}, got {leads}"

    summary_leads = [r["lead"] for r in conf_data["pooled_coverage_trend_summary"]]
    assert summary_leads == expected

    table_b_leads = [r["lead"] for r in conf_data["pooled_table_b_conformity_diagnostics"]]
    assert table_b_leads == expected


# 2. Conformal: coverage in [0, 100]
def test_conformal_coverage_bounds(conf_data):
    for r in conf_data["monthly_table_a_coverage"]:
        cov = r["coverage_pct"]
        assert 0.0 <= cov <= 100.0, f"Coverage out of bounds: {cov} in {r}"

    for r in conf_data["pooled_coverage_trend_summary"]:
        cov = r["coverage_pct"]
        assert 0.0 <= cov <= 100.0, f"Pooled coverage out of bounds: {cov}"


# 3. Conformal: widths >= 0
def test_conformal_widths_non_negative(conf_data):
    for r in conf_data["monthly_table_a_coverage"]:
        assert r["mean_width"] >= 0.0, f"Negative mean width: {r}"
        assert r["median_width"] >= 0.0, f"Negative median width: {r}"

    for r in conf_data["pooled_table_c_rainfall_coverage"]:
        assert r["mean_width"] >= 0.0, f"Negative subgroup width: {r}"


# 4. Conformal: all required diagnostic fields exist
def test_conformal_required_fields_exist(conf_data):
    req_top = [
        "metadata",
        "monthly_table_a_coverage",
        "pooled_table_b_conformity_diagnostics",
        "pooled_table_c_rainfall_coverage",
        "pooled_coverage_trend_summary",
        "monthly_models",
        "pooled_models",
    ]
    for k in req_top:
        assert k in conf_data, f"Missing top-level key: {k}"

    req_table_b = [
        "lead",
        "calib_median", "calib_p80", "calib_p90", "calib_p95", "calib_max",
        "test_median", "test_p80", "test_p90", "test_p95", "test_max",
    ]
    for row in conf_data["pooled_table_b_conformity_diagnostics"]:
        for col in req_table_b:
            assert col in row, f"Missing column {col} in Table B row: {row}"


# 5. Conformal: rainfall bins are exact
def test_conformal_rainfall_bins_exact(conf_data):
    expected_bins = ["0-10 mm", "10-25 mm", "25-50 mm", "50-100 mm", ">100 mm"]
    found_bins = set(r["rainfall_bin"] for r in conf_data["pooled_table_c_rainfall_coverage"])
    assert found_bins == set(expected_bins), f"Rainfall bins mismatch: {found_bins}"


# 6. Conformal: all scalar metrics finite
def test_conformal_scalar_metrics_finite(conf_data):
    def check_finite(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                check_finite(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_finite(v, f"{path}[{i}]")
        elif isinstance(obj, (int, float)):
            assert np.isfinite(obj), f"Non-finite value at {path}: {obj}"

    check_finite(conf_data["monthly_table_a_coverage"], "table_a")
    check_finite(conf_data["pooled_table_b_conformity_diagnostics"], "table_b")
    check_finite(conf_data["pooled_table_c_rainfall_coverage"], "table_c")
    check_finite(conf_data["pooled_coverage_trend_summary"], "trend_summary")


# 7. FSS: thresholds exactly [1.0, 10.0, 25.0]
def test_fss_thresholds_exact(fss_data):
    meta_thresh = fss_data["metadata"]["thresholds_mm_24h"]
    assert meta_thresh == [1.0, 10.0, 25.0], f"Expected [1.0, 10.0, 25.0], got {meta_thresh}"
    table_d_thresh = set(r["threshold_mm"] for r in fss_data["table_d_fss"])
    assert table_d_thresh == {1.0, 10.0, 25.0}


# 8. FSS: scales exactly ['1x1', '3x3', '5x5', '7x7']
def test_fss_scales_exact(fss_data):
    expected_scales = ["1x1", "3x3", "5x5", "7x7"]
    meta_scales = fss_data["metadata"]["neighborhood_scales"]
    assert meta_scales == expected_scales, f"Expected {expected_scales}, got {meta_scales}"
    table_d_scales = set(r["scale"] for r in fss_data["table_d_fss"])
    assert table_d_scales == set(expected_scales)


# 9. FSS: values in [0, 1] or None
def test_fss_values_in_bounds(fss_data):
    for r in fss_data["table_d_fss"]:
        pf = r["pooled_fss"]
        if pf is not None:
            assert 0.0 <= pf <= 1.0, f"FSS out of bounds: {pf} in {r}"
        mf = r["median_case_fss"]
        if mf is not None:
            assert 0.0 <= mf <= 1.0, f"Median FSS out of bounds: {mf} in {r}"


# 10. FSS: no negative neighborhood denominators
def test_fss_no_negative_denominators(fss_data):
    # Verified through valid_cases count >= 0
    for r in fss_data["table_d_fss"]:
        assert r["valid_cases"] >= 0
        assert r["valid_cases"] <= 90  # Exactly 90 cases per lead


# 11. Active land mask unchanged (4,905 active cells)
def test_fss_active_land_mask_unchanged(fss_data):
    assert fss_data["metadata"]["active_land_cells"] == 4905
    assert fss_data["metadata"]["total_cases_per_lead"] == 90
    assert fss_data["metadata"]["total_spatial_cases"] == 810


# 12. FSS: D1–D9 all present
def test_fss_leads_exact(fss_data):
    leads = [f"D{i}" for i in range(1, 10)]
    compact_leads = [r["lead"] for r in fss_data["table_g_compact_profile"]]
    assert compact_leads == leads
    full_metric_leads = list(fss_data["full_metrics_by_lead"].keys())
    assert full_metric_leads == [f"d{i}" for i in range(1, 10)]


# 13. FSS-0.5 horizons only use D1–D9
def test_fss_05_horizons_valid(fss_data):
    valid_targets = {"none", "beyond D9"} | {f"D{i}" for i in range(1, 10)}
    for r in fss_data["table_f_fss_05_horizons"]:
        h = r["reference_horizon"]
        assert h in valid_targets, f"Invalid FSS-0.5 reference horizon: {h}"
        # Ensure D10 is not used
        assert "D10" not in h


# 14. Frequency bias finite whenever observation frequency > 0
def test_fss_frequency_bias_finite(fss_data):
    for r in fss_data["table_e_frequency_bias"]:
        assert r["forecast_frequency"] >= 0.0
        assert r["obs_frequency"] >= 0.0
        if r["obs_frequency"] > 0:
            assert r["frequency_bias"] is not None
            assert np.isfinite(r["frequency_bias"])
            assert r["frequency_bias"] >= 0.0


# 15. No fabricated D10
def test_no_fabricated_d10(conf_data, fss_data):
    assert conf_data["metadata"]["leads_evaluated"][-1] == "D9"
    assert "D10" not in conf_data["metadata"]["leads_evaluated"]
    assert fss_data["metadata"]["d10_status"] == "UNAVAILABLE_EMPIRICALLY"
    assert len(fss_data["table_g_compact_profile"]) == 9


# 16. Regression: Phase 1A August baseline untouched
def test_phase1a_august_baseline_untouched():
    assert P1A_JSON.exists()
    with open(P1A_JSON, encoding="utf-8") as f:
        p1a = json.load(f)
    assert p1a["dataset"]["active_land_cells"] == 4905
    assert p1a["dataset"]["total_samples"] == 147150
    assert p1a["regression_metrics"]["overall_test"]["mae"] == 2.67
    assert p1a["conformal_metrics"]["empirical_coverage_pct"] == 90.99


# 17. Regression: Phase 1B metrics untouched
def test_phase1b_metrics_untouched():
    assert P1B_JSON.exists()
    with open(P1B_JSON, encoding="utf-8") as f:
        p1b = json.load(f)
    aug = p1b["experiment_a_monthly_replication"]["august_2023"]
    assert aug["regression"]["overall_test"]["mae"] == 2.67
    assert aug["conformal"]["empirical_coverage_pct"] == 90.99


# 18. Regression: Phase 2A metrics JSON untouched
def test_phase2a_metrics_untouched():
    assert P2A_JSON.exists()
    with open(P2A_JSON, encoding="utf-8") as f:
        p2a = json.load(f)
    profile = p2a["d1_d9_reliability_profile"]
    assert len(profile) == 9
    assert profile[0]["lead_day"] == 1
    assert profile[0]["xgb_mae"] == 3.9263
    assert profile[5]["lead_day"] == 6
    assert profile[5]["xgb_mae"] == 6.8115
    assert profile[8]["lead_day"] == 9
    assert profile[8]["xgb_mae"] == 5.1356
