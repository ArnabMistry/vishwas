"""
backend/test_api.py
FastAPI TestClient Unit & Integration Tests for VISHWAS Backend.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "VISHWAS" in data["engine"]
    assert data["version"] == "1.0.0"

def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["telemetry"] == "CONNECTED"

def test_system_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["nwp_model"] == "NCUM-G"
    assert data["horizontal_resolution"] == "12 km"
    assert data["vertical_levels"] == 70
    assert "CQR" in data["calibration_method"]

def test_forecast_grid():
    # Test valid lead time Day 5
    response = client.get("/api/v1/forecast/grid?lead_time=5")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 840
    assert data["properties"]["lead_time"] == 5

    # Test invalid lead time out of bounds (0 or 11)
    err_resp = client.get("/api/v1/forecast/grid?lead_time=12")
    assert err_resp.status_code == 422 # Pydantic Query validation error

def test_forecast_point_odisha_hotspot():
    response = client.get("/api/v1/forecast/point?lat=20.0&lon=85.0&lead_time=5")
    assert response.status_code == 200
    data = response.json()
    assert data["matched_cell"]["region_name"] == "Odisha Coastal Plain & Offshore"
    assert len(data["time_series"]) == 10
    assert len(data["analogs"]) == 3
    assert data["properties"]["bust_prob"] >= 0.85

def test_explain_treeshap():
    response = client.get("/api/v1/explain?lat=20.0&lon=85.0&lead_time=5")
    assert response.status_code == 200
    data = response.json()
    assert data["region_name"] == "Odisha Coastal Plain & Offshore"
    assert "CAPE" in data["primary_driver"]
    assert "TreeSHAP" in data["physical_narrative"] or "CAPE" in data["physical_narrative"]
    assert len(data["shap_contributions"]) > 0

def test_alerts_dna_barcode():
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    # Check first alert has 10 days of DNA barcode
    assert len(data[0]["dna_barcode"]) == 10
    # Alerts must be sorted by bust_prob descending
    probs = [a["bust_prob"] for a in data]
    assert probs == sorted(probs, reverse=True)

def test_forecast_grid_real_mode():
    response = client.get("/api/v1/forecast/grid?mode=real")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["properties"]["mode"] == "REAL"
    assert len(data["features"]) == 4905
    props = data["features"][0]["properties"]
    assert "bust_risk_score" in props
    assert "cqr_lower" in props
    assert "cqr_upper" in props
    assert "fci" in props

def test_forecast_grid_demo_mode_explicit():
    response = client.get("/api/v1/forecast/grid?mode=demo&lead_time=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) == 840

def test_forecast_point_real_mode():
    # Test point inspection in real mode for a central India point
    response = client.get("/api/v1/forecast/point?lat=20.0&lon=85.0&mode=real&lead_time=1")
    assert response.status_code == 200
    data = response.json()
    assert "matched_cell" in data
    assert "properties" in data
    assert "bust_risk_score" in data["properties"]
    assert data["data_mode"] == "REAL"
    assert "fss_decay" in data
    assert len(data["fss_decay"]) == 9
    assert len(data["time_series"]) == 9


# ==============================================================================
# PHASE 3 PRODUCT INTEGRATION TESTS (PART 20 REQUIREMENTS)
# ==============================================================================

def test_real_grids_d1_to_d9_exist_and_distinct():
    """Verify real D1 to D9 grids return 4,905 cells with lead-specific metadata."""
    init_dates = set()
    precip_sums = {}

    for lt in range(1, 10):
        resp = client.get(f"/api/v1/forecast/grid?mode=real&lead_time={lt}")
        assert resp.status_code == 200, f"D+{lt} failed with code {resp.status_code}"
        grid = resp.json()
        assert grid["type"] == "FeatureCollection"
        assert len(grid["features"]) == 4905, f"D+{lt} cell count != 4905"

        meta = grid.get("properties", {})
        assert meta["lead_time"] == lt
        assert meta["lead_time_hours"] == lt * 24
        assert meta["mode"] == "REAL"
        assert "NOAA" in meta["model"]
        assert "IMD" in meta["observation_source"]

        init_dates.add(meta["reference_time"])
        total_p = sum(f["properties"]["f_precip"] for f in grid["features"])
        precip_sums[lt] = total_p

        # Check core properties
        first_props = grid["features"][0]["properties"]
        assert "lat" in first_props
        assert "lon" in first_props
        assert "f_precip" in first_props
        assert "predicted_error" in first_props
        assert "cqr_lower" in first_props
        assert "cqr_upper" in first_props
        assert "cqr_bounds" in first_props
        assert "bust_risk_score" in first_props
        assert "fci" in first_props
        assert "shap_drivers" in first_props

    # 9 distinct reference initialization dates (2023-08-27 down to 2023-08-19)
    assert len(init_dates) == 9, f"Expected 9 distinct initialization dates, got {len(init_dates)}"
    # Distinct precipitation totals across leads
    assert len(set(round(p, 1) for p in precip_sums.values())) == 9


def test_real_grid_d10_returns_explicit_422():
    """Verify D10 in REAL mode explicitly returns HTTP 422, never silent D1 fallback."""
    resp = client.get("/api/v1/forecast/grid?mode=real&lead_time=10")
    assert resp.status_code == 422
    data = resp.json()
    assert "D+10 is not empirically available" in data["detail"]


def test_real_point_d1_to_d9_matching():
    """Verify real point endpoint retrieves matching cell across D1..D9 with consistency."""
    for lt in [1, 2, 5, 9]:
        resp = client.get(f"/api/v1/forecast/point?lat=20.25&lon=85.5&lead_time={lt}&mode=real")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_mode"] == "REAL"
        assert data["current_lead_time"] == lt
        props = data["properties"]
        assert "bust_risk_score" in props
        assert props["lead_time"] == lt


def test_real_point_time_series_d1_to_d9():
    """Verify real point time series has exactly D1 to D9, distinct values, no fabrication."""
    resp = client.get("/api/v1/forecast/point?lat=22.0&lon=82.0&lead_time=1&mode=real")
    assert resp.status_code == 200
    data = resp.json()
    ts = data["time_series"]
    assert len(ts) == 9, f"Expected exactly 9 leads in REAL time_series, got {len(ts)}"

    lead_days = [entry["lead_time"] for entry in ts]
    assert lead_days == list(range(1, 10))

    # Verify each entry has required fields
    for entry in ts:
        assert "lead_time" in entry
        assert "valid_time" in entry
        assert "f_precip" in entry
        assert "predicted_error" in entry
        assert "cqr_lower" in entry
        assert "cqr_upper" in entry
        assert "bust_risk_score" in entry
        assert "fci" in entry


def test_real_fss_decay_metrics():
    """Verify real point endpoint exposes validated Phase 2B FSS curve and metadata."""
    resp = client.get("/api/v1/forecast/point?lat=20.0&lon=85.0&mode=real")
    assert resp.status_code == 200
    data = resp.json()

    fss = data["fss_decay"]
    assert len(fss) == 9, f"Expected 9 FSS values, got {len(fss)}"
    # Validated Phase 2B values for 10mm, 5x5: D1 ~ 0.7471, D9 ~ 0.5453
    d1_val = fss[0]["fss"] if isinstance(fss[0], dict) else fss[0]
    d9_val = fss[8]["fss"] if isinstance(fss[8], dict) else fss[8]
    assert 0.70 < d1_val < 0.80, f"Unexpected D1 FSS: {d1_val}"
    assert 0.50 < d9_val < 0.60, f"Unexpected D9 FSS: {d9_val}"

    meta = data["fss_metadata"]
    assert meta["threshold_mm"] == 10.0
    assert meta["neighborhood_scale"] == "5x5"
    assert "Phase 2B" in meta["source"]
    assert "Regional / pooled" in meta["scope"]
    assert meta["reference_limit"] == 0.5


def test_real_status_truthful():
    """Verify REAL status endpoint makes no false claims of operational NCUM-G telemetry."""
    resp = client.get("/api/v1/status?mode=real")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HISTORICAL_VALIDATION"
    assert "NOAA-GFS" in data["nwp_model"]
    assert "NOT CONNECTED" in data["telemetry_status"]
    assert "Split Conformal" in data["calibration_method"]


def test_real_alerts_deterministic():
    """Verify REAL alerts endpoint returns historical validation alerts without fake telemetry."""
    resp = client.get("/api/v1/alerts?mode=real")
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) >= 5

    for alert in alerts:
        assert "Historical Validation" in alert["region_name"]
        assert len(alert["dna_barcode"]) == 10
        # D10 is marked 0.0 (unavailable)
        assert alert["dna_barcode"][9] == 0.0
        # D1..D9 are valid derived risk scores
        for score in alert["dna_barcode"][:9]:
            assert 0.0 <= score <= 1.0


def test_demo_mode_preserved_completely():
    """Verify DEMO mode remains 100% functional with 10 synthetic leads and original data."""
    resp_grid = client.get("/api/v1/forecast/grid?mode=demo&lead_time=10")
    assert resp_grid.status_code == 200
    assert len(resp_grid.json()["features"]) == 840

    resp_point = client.get("/api/v1/forecast/point?lat=20.0&lon=85.0&lead_time=5&mode=demo")
    assert resp_point.status_code == 200
    pdata = resp_point.json()
    assert pdata["data_mode"] == "DEMO"
    assert len(pdata["time_series"]) == 10

    resp_status = client.get("/api/v1/status?mode=demo")
    assert resp_status.status_code == 200
    sdata = resp_status.json()
    assert sdata["status"] == "OPERATIONAL"
    assert sdata["nwp_model"] == "NCUM-G"

