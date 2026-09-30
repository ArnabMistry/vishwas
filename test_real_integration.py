"""Automated integration test for VISHWAS DEMO vs REAL data modes."""

import os
import sys
import time
import json
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_api_modes(base_url="http://127.0.0.1:8000"):
    print("\n--- Verifying FastAPI Backend Endpoints ---")
    
    # 1. Healthz
    with urllib.request.urlopen(f"{base_url}/healthz") as r:
        res = json.loads(r.read())
        assert res["status"] == "ok"
        print("  [PASS] /healthz: OK")
        
    # 2. Demo mode grid (default)
    with urllib.request.urlopen(f"{base_url}/api/v1/forecast/grid?lead_time=1") as r:
        res = json.loads(r.read())
        assert res["type"] == "FeatureCollection"
        assert len(res["features"]) == 840
        print(f"  [PASS] Demo Grid: {len(res['features'])} features (synthetic)")
        
    # 3. Explicit Demo mode
    with urllib.request.urlopen(f"{base_url}/api/v1/forecast/grid?lead_time=1&mode=demo") as r:
        res = json.loads(r.read())
        assert len(res["features"]) == 840
        print("  [PASS] Explicit Demo Grid: 840 features")
        
    # 4. Real mode grid
    with urllib.request.urlopen(f"{base_url}/api/v1/forecast/grid?mode=real") as r:
        res = json.loads(r.read())
        assert res["type"] == "FeatureCollection"
        assert res["properties"]["mode"] == "REAL"
        assert len(res["features"]) == 4905
        props = res["features"][0]["properties"]
        assert "bust_risk_score" in props
        assert "cqr_lower" in props
        assert "cqr_upper" in props
        assert "fci" in props
        assert "shap_drivers" in props
        print(f"  [PASS] Real Mode Grid: {len(res['features'])} features (mode={res['properties']['mode']})")
        
    # 5. Real mode point inspection
    with urllib.request.urlopen(f"{base_url}/api/v1/forecast/point?lat=20.0&lon=85.0&mode=real") as r:
        res = json.loads(r.read())
        assert "matched_cell" in res
        assert "properties" in res
        assert "bust_risk_score" in res["properties"]
        print(f"  [PASS] Real Point Inspection: Matched {res['matched_cell']['region_name']}")

def test_browser_mode(mode: str, port: int = 3000):
    print(f"\n--- Testing Browser UI for Mode: {mode} ---")
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots", "integration")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    viewports = [
        {"name": "desktop", "width": 1440, "height": 900},
        {"name": "tablet", "width": 1024, "height": 768},
        {"name": "mobile", "width": 375, "height": 667}
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for vp in viewports:
            vp_name = vp["name"]
            print(f"  > Viewport: {vp_name} ({vp['width']}x{vp['height']})")
            context = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()
            
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))
            
            page.goto(f"http://localhost:{port}", wait_until="domcontentloaded")
            page.wait_for_selector("header", timeout=12000)
            time.sleep(2)
            
            # 1. Header & Badge Check
            header = page.locator("header")
            assert header.is_visible(), "Header is not visible"
            header_text = header.inner_text()
            assert "VISHWAS" in header_text
            
            badge = page.locator("#data-mode-indicator")
            assert badge.is_visible(), "Data mode badge not visible"
            badge_text = badge.inner_text()
            if mode.upper() == "REAL":
                assert "[REAL DATA: AUG 2023]" in badge_text, f"Expected real data badge, got {badge_text}"
            else:
                assert "[SYNTHETIC DEMO]" in badge_text, f"Expected demo badge, got {badge_text}"
            print(f"    [PASS] Badge verified: '{badge_text}'")
            
            # 2. Map rendering check
            page.wait_for_selector("canvas.maplibregl-canvas", timeout=15000)
            map_canvas = page.locator("canvas.maplibregl-canvas")
            assert map_canvas.is_visible(), "Map canvas not visible"
            print("    [PASS] MapLibre canvas is rendered and active")

            
            # 3. Screenshot
            shot_path = os.path.join(screenshots_dir, f"{mode.lower()}_{vp_name}.png")
            page.screenshot(path=shot_path)
            print(f"    [PASS] Screenshot saved: {shot_path}")
            
            # Check console errors (ignoring webgl warning if headless)
            fatal_errors = [e for e in console_errors if "favicon" not in e.lower() and "404" not in e]
            assert len(fatal_errors) == 0, f"Encountered console errors: {fatal_errors}"
            
            context.close()
        browser.close()
    print(f"  [PASS] All viewports verified cleanly for {mode} mode.")

if __name__ == "__main__":
    test_api_modes()
    print("\nAPI integration tests passed successfully.")
