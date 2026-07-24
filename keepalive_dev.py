import os
import sys
import shutil
import asyncio
import aiohttp
from playwright.sync_api import sync_playwright

DEV_USER = os.environ.get("DEV_USER", "")
DEV_PASS = os.environ.get("DEV_PASS", "")

SIGNON_URL = "https://signon.servicenow.com/x_snc_sso_auth.do?pageId=login&redirectUri=https%3A%2F%2Fdeveloper.servicenow.com%2Fdev.do"
DEV_BASE = "https://developer.servicenow.com"

PROOF_DIR = "proof_dev"

WAKE_TIMEOUT_S = 60


def fail(msg: str):
    print(f"[DEV][FAIL] {msg}")
    sys.exit(1)


def shot(page, name: str):
    path = os.path.join(PROOF_DIR, name)
    page.screenshot(path=path, full_page=True)
    print(f"[DEV][INFO] Screenshot: {path}")


def browser_login() -> list:
    """Log into developer.servicenow.com via Playwright, return cookies."""
    print(f"[DEV][INFO] Opening SSO login page...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(SIGNON_URL, timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        shot(page, "1_login_page.png")

        # wait for the Okta JS to render the username field
        print("[DEV][INFO] Waiting for username field...")
        try:
            page.wait_for_selector(
                "input[name='identifier'], #username, input[type='email'], input[autocomplete='username']",
                timeout=WAKE_TIMEOUT_S * 1000,
            )
        except Exception:
            shot(page, "fail_no_username_field.png")
            browser.close()
            fail(f"Username field never appeared. URL: {page.url}")

        # fill username
        username_sel = page.locator(
            "input[name='identifier'], #username, input[type='email'], input[autocomplete='username']"
        ).first
        username_sel.fill(DEV_USER)
        print(f"[DEV][INFO] Filled username.")

        # click Next/Continue to advance to password screen
        print("[DEV][INFO] Clicking Next...")
        next_btn = page.locator(
            "input[type='submit'], button[type='submit'], [data-se='o-form-input-submit']"
        ).first
        next_btn.click()

        # wait for password field to appear
        print("[DEV][INFO] Waiting for password field...")
        try:
            page.wait_for_selector(
                "input[name='credentials.passcode'], input[type='password'], #password",
                timeout=30000,
            )
        except Exception:
            shot(page, "fail_no_password_field.png")
            browser.close()
            fail(f"Password field never appeared after clicking Next. URL: {page.url}")

        password_sel = page.locator(
            "input[name='credentials.passcode'], input[type='password'], #password"
        ).first
        password_sel.fill(DEV_PASS)
        shot(page, "2_form_filled.png")

        # click the Verify/Sign In button on the password screen
        print("[DEV][INFO] Submitting password...")
        submit_btn = page.locator(
            "input[type='submit'], button[type='submit'], [data-se='o-form-input-submit']"
        ).first
        submit_btn.click()

        try:
            page.wait_for_url("**/developer.servicenow.com/**", timeout=60000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        shot(page, "3_after_submit.png")

        current_url = page.url.lower()
        content = page.content().lower()

        if "invalid" in content or "incorrect" in content or (
            "signon" in current_url and "password" in content
        ):
            shot(page, "fail_wrong_creds.png")
            browser.close()
            fail("Login failed — check DEV_USER and DEV_PASS.")

        if "developer.servicenow.com" not in current_url:
            shot(page, "fail_unexpected_page.png")
            browser.close()
            fail(f"Didnt land on developer.servicenow.com. Got: {page.url}")

        shot(page, "4_dev_portal_landed.png")
        print(f"[DEV][INFO] Logged in. Landed on: {page.url}")

        # extract cookies for aiohttp
        cookies = page.context.cookies()
        browser.close()

    return cookies


async def touch_dev_portal(cookies: list) -> None:
    """Use aiohttp with browser cookies to call the keepalive endpoints."""
    jar = aiohttp.CookieJar()
    for c in cookies:
        jar.update_cookies({c["name"]: c["value"]})

    dev_headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{DEV_BASE}/dev.do",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        print("[DEV][INFO] Calling check_instance_awake...")
        async with session.get(
            f"{DEV_BASE}/api/snc/v1/dev/check_instance_awake",
            headers=dev_headers,
        ) as resp:
            print(f"[DEV][INFO] check_instance_awake -> {resp.status}")

        print("[DEV][INFO] Calling touch-session...")
        async with session.get(
            f"{DEV_BASE}/api/now/uisession/touch-session",
            headers=dev_headers,
        ) as resp:
            print(f"[DEV][INFO] touch-session -> {resp.status}")


async def run():
    if not all([DEV_USER, DEV_PASS]):
        fail("Missing DEV_USER or DEV_PASS env vars.")

    if os.path.exists(PROOF_DIR):
        shutil.rmtree(PROOF_DIR)
    os.makedirs(PROOF_DIR, exist_ok=True)

    # browser_login uses sync Playwright — must run in a thread to avoid
    # "Sync API inside asyncio loop" error when called from async context
    loop = asyncio.get_event_loop()
    cookies = await loop.run_in_executor(None, browser_login)
    await touch_dev_portal(cookies)
    print("[DEV][SUCCESS] Dev portal keep-alive done.")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
