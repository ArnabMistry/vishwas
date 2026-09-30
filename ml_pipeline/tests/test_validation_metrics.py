"""Unit tests for VISHWAS August 2023 D1 validation metrics and diagnostics integrity."""

import json
from pathlib import Path
import numpy as np
import pytest


@pytest.fixture(scope="module")
def validation_metrics():
    metrics_path = Path("ml_pipeline/real_data/aug2023_d1_validation_metrics.json")
    assert metrics_path.exists(), f"Metrics file missing: {metrics_path}"
    with open(metrics_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_finite_values(validation_metrics):
    """Verify all metrics in JSON are finite and contain no NaN or Inf."""
    def check_finite(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                check_finite(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_finite(v, f"{path}[{i}]")
        elif isinstance(obj, (int, float)):
            assert np.isfinite(obj), f"Non-finite at {path}: {obj}"

    check_finite(validation_metrics)


def test_confusion_matrix_total(validation_metrics):
    """Verify TP + TN + FP + FN equals test-set size (24,525) for all decision rules."""
    test_samples = validation_metrics["split"]["test"]["samples"]
    assert test_samples == 24525

    bust_metrics = validation_metrics["bust_metrics"]
    for rule_name in ["primary_decision_rule", "operational_alert_rule", "conformal_upper_bound_rule"]:
        assert rule_name in bust_metrics
        m = bust_metrics[rule_name]["metrics"]
        total = m["tp"] + m["tn"] + m["fp"] + m["fn"]
        assert total == test_samples, f"{rule_name} total {total} != {test_samples}"


def test_rainfall_stratification_coverage(validation_metrics):
    """Verify rainfall-intensity bins cover the test set exactly with no gaps or overlap."""
    test_samples = validation_metrics["split"]["test"]["samples"]
    strat = validation_metrics["rainfall_stratification"]
    
    expected_bins = ["0–10 mm", "10–25 mm", "25–50 mm", "50–100 mm", ">100 mm"]
    for b in expected_bins:
        assert b in strat, f"Missing bin {b}"

    total_strat = sum(v["sample_count"] for v in strat.values())
    assert total_strat == test_samples


def test_regression_improvement(validation_metrics):
    """Verify XGBoost improves upon naive median baseline on both MAE and RMSE."""
    base_mae = validation_metrics["regression_metrics"]["baseline"]["mae"]
    base_rmse = validation_metrics["regression_metrics"]["baseline"]["rmse"]
    xgb_mae = validation_metrics["regression_metrics"]["overall_test"]["mae"]
    xgb_rmse = validation_metrics["regression_metrics"]["overall_test"]["rmse"]

    assert xgb_mae < base_mae
    assert xgb_rmse < base_rmse
    assert xgb_mae == pytest.approx(2.6700, abs=1e-3)
    assert xgb_rmse == pytest.approx(6.4008, abs=1e-3)


def test_conformal_coverage_bounds(validation_metrics):
    """Verify conformal nominal and empirical coverages are valid."""
    conf = validation_metrics["conformal_metrics"]
    assert conf["nominal_coverage_pct"] == 80.0
    assert conf["empirical_coverage_pct"] >= 80.0
    assert conf["empirical_coverage_pct"] == pytest.approx(90.99, abs=0.1)
