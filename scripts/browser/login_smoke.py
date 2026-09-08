"""Login/guard flow smoke test in a real Chromium:

  1. login page renders
  2. demo admin login -> token stored
  3. redirect off /login after auth
  4. dashboard body renders
  5. reload / stays authenticated
  6. cleared token -> / redirects to /login
  7. protected API without token -> 401
  8. logout button returns to /login

Usage: python scripts/browser/login_smoke.py [base_url]
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.goto(f"{BASE}/login", wait_until="networkidle")
        check("login page renders",
              page.locator("input").count() >= 1,
              f"url={page.url}")

        inputs = page.locator("input")
        n = inputs.count()
        both_ok = False
        if n >= 2:
            inputs.nth(0).fill("admin@airindex.gov.in")
            inputs.nth(1).fill("change-me-immediately")
            page.locator("button[type='submit'], form button").first.click()
            page.wait_for_timeout(3000)
            keys = page.evaluate("() => Object.keys(localStorage)")
            both_ok = "airindex_access_token" in keys
        check("login form submit -> token stored", both_ok, f"url_after={page.url}")

        check("redirected off /login after auth",
              not page.url.rstrip("/").endswith("/login"), f"url={page.url}")

        body = page.inner_text("body")
        check("dashboard body has content", len(body.strip()) > 50, f"chars={len(body.strip())}")

        page.goto(f"{BASE}/", wait_until="networkidle")
        check("reload / stays authenticated",
              not page.url.rstrip("/").endswith("/login"), f"url={page.url}")
        page.wait_for_timeout(500)

        page.evaluate("() => localStorage.clear()")
        page.goto(f"{BASE}/", wait_until="networkidle")
        check("no token -> / redirects to /login",
              page.url.rstrip("/").endswith("/login"), f"url={page.url}")

        resp = page.request.get(f"{API}/api/auth/me")
        check("API /auth/me without token -> 401", resp.status == 401, f"status={resp.status}")

        page.locator("input").nth(0).fill("admin@airindex.gov.in")
        page.locator("input").nth(1).fill("change-me-immediately")
        page.locator("button[type='submit'], form button").first.click()
        page.wait_for_timeout(3000)
        btns = page.locator("button")
        logout_found = False
        for i in range(btns.count()):
            t = (btns.nth(i).inner_text() or "").strip().lower()
            if "logout" in t or "sign out" in t:
                logout_found = True
                btns.nth(i).click()
                break
        page.wait_for_timeout(2000)
        check("logout button works -> /login",
              logout_found and page.url.rstrip("/").endswith("/login"),
              f"found={logout_found}, url={page.url}")

        browser.close()

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== {passed}/{total} checks passed ===")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()