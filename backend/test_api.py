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
    response = client.get("/api/v1/forecast/point?lat=20.0&lon=85.0&mode=real")
    assert response.status_code == 200
    data = response.json()
    assert "matched_cell" in data
    assert "properties" in data
    assert "bust_risk_score" in data["properties"]

