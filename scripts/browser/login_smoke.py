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

EMAIL = "admin@airindex.gov.in"
PASSWORD = "change-me-immediately"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def _login(page):
    """Drive the two-step login form: email -> continue -> password -> sign in."""
    page.goto(f"{BASE}/login", wait_until="networkidle")

    # Step 1: email
    page.locator("input#email").fill(EMAIL)
    page.locator("button[type='submit']").click()
    page.wait_for_selector("input#password", state="visible", timeout=5000)

    # Step 2: password (for existing users the username field is hidden)
    page.locator("input#password").fill(PASSWORD)
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(3000)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # --- 1. login page renders ---
        page.goto(f"{BASE}/login", wait_until="networkidle")
        check("login page renders",
              page.locator("input#email").is_visible(),
              f"url={page.url}")

        # --- 2. login form submit -> token stored ---
        _login(page)
        keys = page.evaluate("() => Object.keys(localStorage)")
        check("login form submit -> token stored",
              "airindex_access_token" in keys,
              f"url_after={page.url}")

        # --- 3. redirected off /login after auth ---
        check("redirected off /login after auth",
              not page.url.rstrip("/").endswith("/login"),
              f"url={page.url}")

        # --- 4. dashboard body has content ---
        body = page.inner_text("body")
        check("dashboard body has content",
              len(body.strip()) > 50,
              f"chars={len(body.strip())}")

        # --- 5. reload / stays authenticated ---
        page.goto(f"{BASE}/", wait_until="networkidle")
        check("reload / stays authenticated",
              not page.url.rstrip("/").endswith("/login"),
              f"url={page.url}")

        # --- 6. no token -> / redirects to /login ---
        page.evaluate("() => localStorage.clear()")
        page.goto(f"{BASE}/", wait_until="networkidle")
        check("no token -> / redirects to /login",
              page.url.rstrip("/").endswith("/login"),
              f"url={page.url}")

        # --- 7. API /auth/me without token -> 401 ---
        resp = page.request.get(f"{API}/api/auth/me")
        check("API /auth/me without token -> 401",
              resp.status == 401,
              f"status={resp.status}")

        # --- 8. logout button works -> /login ---
        _login(page)
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
