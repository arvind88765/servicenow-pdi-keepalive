import os
import sys
import shutil
import asyncio
import aiohttp
from playwright.sync_api import sync_playwright

DEV_USER = os.environ.get("DEV_USER", "")
DEV_PASS = os.environ.get("DEV_PASS", "")

# userlogin.do triggers the full SSO redirect chain through Okta
SIGNON_URL = "https://developer.servicenow.com/userlogin.do?relayState=https%3A%2F%2Fdeveloper.servicenow.com%2Fdev.do"
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
        # don't wait for networkidle here — the SAML auto-submit chain
        # takes multiple redirects before the Okta widget appears
        shot(page, "1_login_page.png")

        # wait for whichever login form loads — classic Okta widget (#okta-signin-username)
        # or IDX-based form (input[name="identifier"]) — depends on routing
        print("[DEV][INFO] Waiting for Okta login form...")
        USERNAME_SEL = "#okta-signin-username, input[name='identifier'], input[autocomplete='username']"
        PASSWORD_SEL = "#okta-signin-password, input[name='credentials.passcode'], input[type='password']"
        SUBMIT_SEL = "#okta-signin-submit, input[value='Sign In'], button[data-se='o-form-input-submit'], input[type='submit']"
        try:
            page.wait_for_selector(USERNAME_SEL, timeout=WAKE_TIMEOUT_S * 1000)
        except Exception:
            shot(page, "fail_no_login_form.png")
            browser.close()
            fail(f"Login form never appeared. URL: {page.url}")

        shot(page, "1_login_page.png")
        page.locator(USERNAME_SEL).first.fill(DEV_USER)

        # IDX shows username first then password on next step; classic widget shows both at once
        # try filling password immediately — if it's not visible yet, click Next first
        try:
            page.wait_for_selector(PASSWORD_SEL, timeout=3000)
            page.locator(PASSWORD_SEL).first.fill(DEV_PASS)
        except Exception:
            # password not visible yet — click Next/Submit to advance to password step
            print("[DEV][INFO] Password not visible, clicking Next...")
            page.locator(SUBMIT_SEL).first.click()
            page.wait_for_selector(PASSWORD_SEL, timeout=30000)
            page.locator(PASSWORD_SEL).first.fill(DEV_PASS)

        print(f"[DEV][INFO] Filled credentials.")
        shot(page, "2_form_filled.png")

        print("[DEV][INFO] Clicking Sign In...")
        page.locator(SUBMIT_SEL).first.click()

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
