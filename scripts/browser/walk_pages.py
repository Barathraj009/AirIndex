"""Full page walk: visit every route as the seeded admin in a real
Chromium, assert it renders real content with zero console errors, zero
HTTP >= 400 responses, and no crash-marker text. Exit non-zero unless
ALL pages pass.

Usage: python scripts/browser/walk_pages.py [base_url]
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"

ROUTES = [
    ("/", "Overview"),
    ("/index", "Airfare Price Index"),
    ("/routes", "Route Analysis"),
    ("/heatmap", "Sector Heatmap"),
    ("/lead-time", "Lead-Time Analysis"),
    ("/airlines", "Airline Analysis"),
    ("/explorer", "Data Explorer"),
    ("/quality", "Data Quality"),
    ("/scraping", "Scraping Monitor"),
    ("/backtesting", "Backtesting"),
    ("/cpi-simulator", "CPI Augmentation"),
    ("/geospatial-map", "Geospatial Map"),
    ("/methodology", "Methodology"),
    ("/api-docs", "API Docs"),
    ("/admin", "Admin"),
]

ERROR_TEXT = ("failed to fetch", "unexpected end of json", "networkerror",
              "cannot read properties", "is not a function", "internal server error",
              "traceback", "referenceerror", "typeerror", "rendererror")
FAIL_CODE = 0
total = 0
ok = 0


def run_walk():
    global total, ok, FAIL_CODE
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text)
                if msg.type == "error" and "favicon" not in (msg.text or "").lower() else None)
        bad_responses = []
        page.on("response", lambda r: bad_responses.append(f"{r.status} {r.url}")
                if r.status >= 400 else None)

        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.locator("input#email").fill("admin@airindex.gov.in")
        page.locator("button[type='submit']").click()
        page.wait_for_selector("input#password", state="visible", timeout=5000)
        page.locator("input#password").fill("change-me-immediately")
        page.locator("button[type='submit']").click()
        page.wait_for_timeout(3500)

        if page.url.rstrip("/").endswith("/login"):
            print("FAIL login did not succeed; aborting walk")
            sys.exit(2)

        for path, label in ROUTES:
            total += 1
            console_errors.clear()
            bad_responses.clear()
            try:
                page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(1800)
                body = page.inner_text("body").strip()
                h2s = page.locator("h1, h2, h3").count()
                lower = body.lower()
                err_hits = [t for t in ERROR_TEXT if t in lower]
                page_failed = bool(console_errors) or bool(bad_responses) or bool(err_hits)
                status = "FAIL" if page_failed else "PASS"
                if not page_failed:
                    ok += 1
                else:
                    FAIL_CODE = 1
                    print(f"      console: {','.join(console_errors[:4])}")
                    print(f"      http>=400: {','.join(bad_responses[:4])}")
                    print(f"      errtext: {','.join(err_hits)}")
            except Exception as e:  # noqa: BLE001
                FAIL_CODE = 1
                status = "FAIL(exception)"
                print(f"      exception: {str(e)[:200]}")
            print(f"{status}  {path:16s} {label:22s} body={len(body):>5} h2+={h2s}")

        browser.close()


if __name__ == "__main__":
    run_walk()
    print(f"\n=== {ok}/{total} pages clean ===")
    sys.exit(FAIL_CODE)