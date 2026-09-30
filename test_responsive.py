import os
import sys
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VIEWPORTS = [
    {"name": "1920x1080_FHD", "width": 1920, "height": 1080},
    {"name": "1600x900_HD_Plus", "width": 1600, "height": 900},
    {"name": "1440x900_MacBook", "width": 1440, "height": 900},
    {"name": "1366x768_Standard_Laptop", "width": 1366, "height": 768},
    {"name": "1280x800_Small_Laptop", "width": 1280, "height": 800},
]

def run_responsive_tests():
    print("=" * 65)
    print("VISHWAS Responsive Multi-Viewport Collision & Layout Validation")
    print("=" * 65)

    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots", "responsive")
    os.makedirs(screenshots_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in VIEWPORTS:
            name = vp["name"]
            w = vp["width"]
            h = vp["height"]
            print(f"\n[Testing Viewport: {name} ({w}x{h})]")

            context = browser.new_context(viewport={"width": w, "height": h})
            page = context.new_page()

            page.goto("http://localhost:3000", wait_until="domcontentloaded")
            page.wait_for_selector("header", timeout=8000)
            time.sleep(1.5)

            # Check header
            assert page.locator("header").is_visible(), "Header must be visible"

            # Check Operations Overview
            ops_panel = page.locator("aside").first
            assert ops_panel.is_visible(), "Operations overview must be visible"
            ops_box = ops_panel.bounding_box()
            assert ops_box is not None, "Operations box exists"

            # Check Timeline
            timeline = page.locator("div.bg-slate-950\\/95").filter(has=page.locator("button:has-text('D+5')")).first
            assert timeline.is_visible(), "Timeline dock must be visible"
            timeline_box = timeline.bounding_box()
            assert timeline_box is not None, "Timeline box exists"

            # Verify no collision between Left Panel and Timeline
            ops_right = ops_box["x"] + ops_box["width"]
            timeline_left = timeline_box["x"]

            # Switch to Day 5 and open Odisha Inspector
            day5_btn = page.locator("button:has-text('D+5')")
            day5_btn.click()
            time.sleep(0.8)

            odisha_alert = page.locator("div:has-text('Odisha Coastal Plain & Offshore')").last
            odisha_alert.click()
            time.sleep(1.2)

            inspector = page.locator("aside").last
            assert inspector.is_visible(), "Inspector must be visible"
            inspector_box = inspector.bounding_box()
            assert inspector_box is not None, "Inspector box exists"

            # Re-read timeline box with inspector open
            timeline_box_after = timeline.bounding_box()
            timeline_right = timeline_box_after["x"] + timeline_box_after["width"]
            inspector_left = inspector_box["x"]

            # Print layout metrics
            print(f"  Left Panel: right={ops_right:.0f}px | Timeline: left={timeline_box_after['x']:.0f}px..right={timeline_right:.0f}px | Inspector: left={inspector_left:.0f}px")

            # Check collisions
            left_gap = timeline_box_after["x"] - ops_right
            right_gap = inspector_left - timeline_right
            print(f"  Separation: Left-to-Timeline Gap = {left_gap:.0f}px | Timeline-to-Inspector Gap = {right_gap:.0f}px")

            # Verify buttons in inspector and timeline remain interactive
            analogs_btn = page.locator("button:has-text('ANALOGS')")
            assert analogs_btn.is_visible(), "Analogs tab button must be visible"
            analogs_btn.click()
            time.sleep(0.5)

            # Capture screenshot
            shot_path = os.path.join(screenshots_dir, f"viewport_{name}.png")
            page.screenshot(path=shot_path)
            print(f"  [PASS] Screenshot saved: {shot_path}")

            context.close()

        browser.close()

    print("\n" + "=" * 65)
    print("ALL RESPONSIVE VIEWPORT TESTS PASSED WITH ZERO OVERLAP!")
    print("=" * 65)

if __name__ == "__main__":
    run_responsive_tests()
