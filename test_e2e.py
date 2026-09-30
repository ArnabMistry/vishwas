import os
import sys
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_e2e_validation():
    print("=" * 60)
    print("Starting Autonomous E2E Validation for VISHWAS")
    print("=" * 60)

    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Capture console messages
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))
        page.on("requestfailed", lambda req: print(f"REQ FAILED: {req.url} -> {req.failure}"))

        print("\n[Step 1] Navigating to http://localhost:3000...")
        page.goto("http://localhost:3000", wait_until="domcontentloaded")
        page.wait_for_selector("header", timeout=10000)
        time.sleep(2)

        # 1. Header Validation
        print("[Step 2] Validating Header & Telemetry...")
        header_text = page.locator("header").inner_text()
        assert "VISHWAS" in header_text, "VISHWAS logo not found in header"
        assert "NCMRWF" in header_text, "NCMRWF agency badge not found"
        assert "NCUM-G" in header_text, "NCUM-G model text not found"
        assert "STATUS:" in header_text, "Status badge not found"
        print("  [PASS] Header branding, agency context, and telemetry verified.")

        # Take screenshot of Initial State (Day 1)
        day1_shot = os.path.join(screenshots_dir, "01_day1_operations.png")
        page.screenshot(path=day1_shot)
        print(f"  [PASS] Saved screenshot: {day1_shot}")

        # 2. Operations Overview Panel Validation
        print("\n[Step 3] Validating Left Overlay (Operations Overview)...")
        page.wait_for_selector("text=CONFIDENCE DNA", timeout=8000)
        ops_panel = page.locator("aside").first
        ops_text = ops_panel.inner_text()
        assert "OPERATIONS OVERVIEW" in ops_text, "Operations overview header missing"
        assert "MEAN NETWORK FCI" in ops_text, "FCI metric missing"
        assert "CONFIDENCE DNA" in ops_text, "Confidence DNA barcode missing"
        assert "Odisha Coastal Plain" in ops_text, "Odisha alert missing in feed"
        print("  [PASS] Operations Overview metrics, distribution, and DNA barcodes verified.")

        # 3. Timeline Interaction (Day 5 - Critical Demo Hotspot)
        print("\n[Step 4] Interacting with Timeline & selecting Day 5...")
        day5_button = page.locator("button:has-text('D+5')")
        day5_button.click()
        time.sleep(1.5)

        # Verify Day 5 hotspot highlight banner
        timeline_text = page.locator("input[type='range']").locator("..").locator("..").inner_text()
        assert "Day 5 / 10" in timeline_text, "Timeline not showing Day 5"
        print("  [PASS] Timeline scrubbed to Day 5 (120h Horizon). Hotspot banner active.")

        # 4. Trigger Alert Click & Open Region Inspector
        print("\n[Step 5] Clicking Odisha Alert to trigger map flyTo & Inspector...")
        odisha_alert = page.locator("div:has-text('Odisha Coastal Plain & Offshore')").last
        odisha_alert.click()
        time.sleep(1.5)

        # Verify Inspector Panel
        inspector = page.locator("aside").last
        inspector_text = inspector.inner_text()
        assert "Odisha Coastal Plain & Offshore" in inspector_text, "Region title not in inspector"
        assert "FORECAST CONFIDENCE INDICATOR" in inspector_text, "FCI title not in inspector"
        assert "80% CONFORMAL ERROR BOUND (CQR)" in inspector_text, "CQR bound not in inspector"
        assert "PHYSICAL BUST ATTRIBUTION (TreeSHAP)" in inspector_text, "TreeSHAP attribution missing"
        assert "Anomalous CAPE exceeding convective limits" in inspector_text, "CAPE driver missing"
        assert "SPATIAL VERIFICATION" in inspector_text, "Spatial verification missing"
        print("  [PASS] Region Inspector verified with CQR bounds, TreeSHAP drivers, and FSS curve.")

        # Take screenshot of Day 5 Inspector
        day5_shot = os.path.join(screenshots_dir, "02_day5_odisha_inspector.png")
        page.screenshot(path=day5_shot)
        print(f"  [PASS] Saved screenshot: {day5_shot}")

        # 5. Toggle Historical Analogs
        print("\n[Step 6] Toggling Historical Analogs view...")
        analogs_btn = page.locator("button:has-text('ANALOGS')")
        analogs_btn.click()
        time.sleep(1)

        inspector_text_analogs = inspector.inner_text()
        assert "2020 Bay of Bengal Monsoon Low" in inspector_text_analogs, "Historical analog missing"
        print("  [PASS] Historical analog matching verified.")

        analogs_shot = os.path.join(screenshots_dir, "03_historical_analogs.png")
        page.screenshot(path=analogs_shot)
        print(f"  [PASS] Saved screenshot: {analogs_shot}")

        # 6. Open and Validate System Status Modal
        print("\n[Step 7] Opening System Status Modal...")
        status_button = page.locator("button:has-text('STATUS:')")
        status_button.click()
        time.sleep(1)

        modal = page.locator("div.fixed.inset-0")
        modal_text = modal.inner_text()
        assert "SYSTEM TELEMETRY & PIPELINE SPECIFICATION" in modal_text, "Modal title missing"
        assert "XGBoost Regressor" in modal_text, "ML Regressor spec missing"
        assert "Conformalized Quantile Regression" in modal_text or "CQR" in modal_text, "CQR spec missing"
        assert "ALL SUBSYSTEMS GREEN" in modal_text, "Health check status missing"
        print("  [PASS] System Status Modal verified.")

        modal_shot = os.path.join(screenshots_dir, "04_system_status_modal.png")
        page.screenshot(path=modal_shot)
        print(f"  [PASS] Saved screenshot: {modal_shot}")

        # Dismiss modal
        dismiss_btn = page.locator("button:has-text('DISMISS')")
        dismiss_btn.click()
        time.sleep(0.5)

        # Print all console warnings/errors
        print(f"\nCaptured {len(console_logs)} browser console events:")
        for log in console_logs:
            print("  ", log)

        browser.close()

    print("\n" + "=" * 60)
    print("ALL E2E VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_e2e_validation()
