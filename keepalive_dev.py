import os
import sys
import shutil
import asyncio
import aiohttp
from playwright.sync_api import sync_playwright

DEV_USER = os.environ.get("DEV_USER", "")
DEV_PASS = os.environ.get("DEV_PASS", "")

OKTA_BASE = "https://ssosignon.servicenow.com"
SIGNON_BASE = "https://signon.servicenow.com"
DEV_BASE = "https://developer.servicenow.com"

PROOF_DIR = "proof_dev"

OKTA_HEADERS = {
    "Accept": "application/ion+json; okta-version=1.0.0",
    "Content-Type": "application/ion+json; okta-version=1.0.0",
    "Origin": SIGNON_BASE,
    "x-okta-user-agent-extended": "okta-auth-js/7.11.0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
}

JSON_HEADERS = {
    "Accept": "application/json; okta-version=1.0.0",
    "Content-Type": "application/json",
    "Origin": SIGNON_BASE,
    "x-okta-user-agent-extended": "okta-auth-js/7.11.0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
}


def fail(msg: str):
    print(f"[DEV][FAIL] {msg}")
    sys.exit(1)


def take_screenshot(page, name: str):
    path = os.path.join(PROOF_DIR, name)
    page.screenshot(path=path, full_page=True)
    print(f"[DEV][INFO] Screenshot saved: {path}")


async def get_state_token(session: aiohttp.ClientSession) -> str:
    print("[DEV][INFO] Hitting developer.servicenow.com to grab stateToken...")
    async with session.get(
        f"{DEV_BASE}/dev.do",
        allow_redirects=True,
        max_redirects=10,
    ) as resp:
        final_url = str(resp.url)

    if "stateHandle" not in final_url and "stateToken" not in final_url:
        fail(f"Expected SSO redirect but got: {final_url}")

    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(final_url).query)
    token = qs.get("stateHandle", qs.get("stateToken", [None]))[0]
    if not token:
        fail(f"Couldnt parse stateToken from: {final_url}")
    print("[DEV][INFO] Got stateToken.")
    return token


async def introspect(session: aiohttp.ClientSession, state_token: str) -> str:
    print("[DEV][INFO] Introspecting...")
    async with session.post(
        f"{OKTA_BASE}/idp/idx/introspect",
        json={"stateToken": state_token},
        headers=OKTA_HEADERS,
    ) as resp:
        if resp.status != 200:
            fail(f"introspect failed: {resp.status}")
        data = await resp.json(content_type=None)

    state_handle = data.get("stateHandle")
    if not state_handle:
        fail("No stateHandle in introspect response")
    print("[DEV][INFO] Got stateHandle.")
    return state_handle


async def identify(session: aiohttp.ClientSession, identifier: str, state_handle: str) -> str:
    print(f"[DEV][INFO] Submitting username: {identifier}...")
    async with session.post(
        f"{OKTA_BASE}/idp/idx/identify",
        json={"identifier": identifier, "stateHandle": state_handle},
        headers=JSON_HEADERS,
    ) as resp:
        if resp.status != 200:
            fail(f"identify failed: {resp.status}")
        data = await resp.json(content_type=None)

    new_handle = data.get("stateHandle")
    if not new_handle:
        fail("No stateHandle after identify")
    print("[DEV][INFO] Username accepted.")
    return new_handle


async def challenge_answer(session: aiohttp.ClientSession, passcode: str, state_handle: str) -> str:
    print("[DEV][INFO] Submitting password...")
    async with session.post(
        f"{OKTA_BASE}/idp/idx/challenge/answer",
        json={"credentials": {"passcode": passcode}, "stateHandle": state_handle},
        headers=JSON_HEADERS,
    ) as resp:
        if resp.status != 200:
            fail(f"challenge/answer failed: {resp.status}")
        data = await resp.json(content_type=None)

    success = data.get("successWithInteractionCode", {})
    href = success.get("href") or success.get("value", {}).get("href")
    if not href:
        for item in data.get("remediation", {}).get("value", []):
            if item.get("name") == "issue":
                href = item.get("href")
                break
    if not href:
        fail(f"No redirect href after password. Response keys: {list(data.keys())}")
    print("[DEV][INFO] Password accepted.")
    return href


async def get_cookies_from_redirect(session: aiohttp.ClientSession, href: str) -> list:
    """Follow the OAuth callback and collect cookies for Playwright to use."""
    print("[DEV][INFO] Completing OAuth code exchange...")
    async with session.get(href, allow_redirects=True, max_redirects=15) as resp:
        final_url = str(resp.url)
        if "developer.servicenow.com" not in final_url:
            fail(f"Didnt land on developer.servicenow.com. Got: {final_url}")
        print(f"[DEV][INFO] Logged in. Final URL: {final_url}")

    cookies = []
    for c in session.cookie_jar:
        cookies.append({
            "name": c.key,
            "value": c.value,
            "domain": c.get("domain", ".developer.servicenow.com"),
            "path": c.get("path", "/"),
        })
    return cookies


def take_dev_screenshots(cookies: list):
    """Inject session cookies into Playwright and screenshot the dev portal."""
    print("[DEV][INFO] Opening dev portal in headless browser for screenshots...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()

        valid_cookies = []
        for c in cookies:
            domain = c.get("domain", "")
            if not domain:
                domain = ".developer.servicenow.com"
            if not domain.startswith(".") and not domain.startswith("developer"):
                domain = "." + domain
            valid_cookies.append({
                "name": c["name"],
                "value": c["value"],
                "domain": domain,
                "path": c.get("path", "/"),
            })

        if valid_cookies:
            ctx.add_cookies(valid_cookies)

        page = ctx.new_page()
        page.goto(f"{DEV_BASE}/dev.do", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        take_screenshot(page, "1_dev_portal_home.png")

        page.wait_for_timeout(3000)
        take_screenshot(page, "2_dev_portal_loaded.png")

        current_url = page.url.lower()
        content = page.content().lower()

        if "signon" in current_url or "login" in current_url:
            take_screenshot(page, "3_dev_portal_failed.png")
            browser.close()
            fail("Session cookies didnt work, still on login page.")

        print(f"[DEV][INFO] Dev portal screenshot done. URL: {page.url}")

        page.wait_for_timeout(2000)
        take_screenshot(page, "3_dev_portal_final.png")
        browser.close()


async def touch_dev_portal(session: aiohttp.ClientSession) -> None:
    dev_headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{DEV_BASE}/dev.do",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

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

    connector = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        state_token = await get_state_token(session)
        state_handle = await introspect(session, state_token)
        state_handle = await identify(session, DEV_USER, state_handle)
        href = await challenge_answer(session, DEV_PASS, state_handle)
        cookies = await get_cookies_from_redirect(session, href)
        await touch_dev_portal(session)

    take_dev_screenshots(cookies)
    print("[DEV][SUCCESS] Dev portal keep-alive done.")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
