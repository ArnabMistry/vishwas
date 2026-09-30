import urllib.request
import json
import sys

def verify_all_endpoints():
    base_url = "http://127.0.0.1:8000"
    print("=" * 60)
    print("Starting Automated Backend Verification for VISHWAS")
    print("=" * 60)

    # 1. Health check
    url = f"{base_url}/healthz"
    res = json.loads(urllib.request.urlopen(url).read())
    assert res.get("status") == "ok", f"Health check failed: {res}"
    print(f"[PASS] 1. /healthz: {res}")

    # 2. Status telemetry
    url = f"{base_url}/api/v1/status"
    res_status = json.loads(urllib.request.urlopen(url).read())
    assert res_status.get("status") == "OPERATIONAL", f"Status check failed: {res_status}"
    assert res_status.get("nwp_model") == "NCUM-G", "Model check failed"
    print(f"[PASS] 2. /api/v1/status: NWP={res_status['nwp_model']}, Cycle={res_status['cycle']}, Calibration={res_status['calibration_method']}")

    # 3. Forecast grid lead time D+5
    url = f"{base_url}/api/v1/forecast/grid?lead_time=5"
    res_grid = json.loads(urllib.request.urlopen(url).read())
    assert res_grid.get("type") == "FeatureCollection", "Grid GeoJSON invalid"
    assert len(res_grid.get("features", [])) == 840, f"Expected 840 features, got {len(res_grid.get('features', []))}"
    print(f"[PASS] 3. /api/v1/forecast/grid: Feature count = {len(res_grid['features'])}")

    # 4. Point inspection for Odisha [20.0 N, 85.0 E]
    url = f"{base_url}/api/v1/forecast/point?lat=20.0&lon=85.0&lead_time=5"
    res_point = json.loads(urllib.request.urlopen(url).read())
    assert res_point.get("matched_cell", {}).get("region_name") == "Odisha Coastal Plain & Offshore", "Point matching failed"
    assert len(res_point.get("time_series", [])) == 10, "Expected 10-day time series"
    assert len(res_point.get("analogs", [])) == 3, "Expected 3 analogs"
    print(f"[PASS] 4. /api/v1/forecast/point: Matched region = '{res_point['matched_cell']['region_name']}', TimeSeries len={len(res_point['time_series'])}, Analogs={len(res_point['analogs'])}")

    # 5. TreeSHAP explanation endpoint
    url = f"{base_url}/api/v1/explain?lat=20.0&lon=85.0&lead_time=5"
    res_explain = json.loads(urllib.request.urlopen(url).read())
    assert "CAPE" in res_explain.get("primary_driver", ""), "TreeSHAP explanation missing CAPE"
    print(f"[PASS] 5. /api/v1/explain: Primary driver = '{res_explain['primary_driver']}'")

    # 6. Alerts endpoint
    url = f"{base_url}/api/v1/alerts"
    res_alerts = json.loads(urllib.request.urlopen(url).read())
    assert len(res_alerts) >= 5, "Alerts list too short"
    assert len(res_alerts[0].get("dna_barcode", [])) == 10, "Confidence DNA barcode length != 10"
    print(f"[PASS] 6. /api/v1/alerts: Alert count = {len(res_alerts)}, First hotspot = '{res_alerts[0]['region_name']}' ({res_alerts[0]['bust_prob']*100:.0f}%)")

    print("\n" + "=" * 60)
    print("ALL BACKEND VERIFICATION CHECKS PASSED (6/6)")
    print("=" * 60)

if __name__ == "__main__":
    verify_all_endpoints()
