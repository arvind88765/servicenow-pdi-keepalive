import os
import sys
import asyncio
import aiohttp

DEV_USER = os.environ.get("DEV_USER", "")
DEV_PASS = os.environ.get("DEV_PASS", "")

OKTA_BASE = "https://ssosignon.servicenow.com"
SIGNON_BASE = "https://signon.servicenow.com"
DEV_BASE = "https://developer.servicenow.com"

# app client id from HAR metadata
APP_ID = "0oa1illp62g93zCpl0x8"

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


async def get_state_token(session: aiohttp.ClientSession) -> str:
    """Hit developer.servicenow.com/dev.do, follow the redirect to signon,
    and pull the stateToken from the redirect URL query param."""
    print("[DEV][INFO] Opening developer.servicenow.com to get stateToken...")
    async with session.get(
        f"{DEV_BASE}/dev.do",
        allow_redirects=True,
        max_redirects=10,
    ) as resp:
        final_url = str(resp.url)

    if "stateHandle" not in final_url and "stateToken" not in final_url:
        fail(f"Did not get redirected to SSO login. Final URL: {final_url}")

    # stateToken is the whole value after ?stateHandle= in the redirect URL
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(final_url).query)
    token = qs.get("stateHandle", qs.get("stateToken", [None]))[0]
    if not token:
        fail(f"Could not parse stateToken from URL: {final_url}")
    print("[DEV][INFO] Got stateToken.")
    return token


async def introspect(session: aiohttp.ClientSession, state_token: str) -> str:
    """POST /idp/idx/introspect with stateToken → returns stateHandle for next steps."""
    print("[DEV][INFO] Introspecting state token...")
    async with session.post(
        f"{OKTA_BASE}/idp/idx/introspect",
        json={"stateToken": state_token},
        headers=OKTA_HEADERS,
    ) as resp:
        if resp.status != 200:
            fail(f"introspect failed with status {resp.status}")
        data = await resp.json(content_type=None)

    state_handle = data.get("stateHandle")
    if not state_handle:
        fail("No stateHandle in introspect response")
    print("[DEV][INFO] Got stateHandle.")
    return state_handle


async def identify(session: aiohttp.ClientSession, identifier: str, state_handle: str) -> str:
    """POST /idp/idx/identify with username → returns new stateHandle for challenge step."""
    print(f"[DEV][INFO] Identifying user: {identifier}...")
    async with session.post(
        f"{OKTA_BASE}/idp/idx/identify",
        json={"identifier": identifier, "stateHandle": state_handle},
        headers=JSON_HEADERS,
    ) as resp:
        if resp.status != 200:
            fail(f"identify failed with status {resp.status}")
        data = await resp.json(content_type=None)

    new_handle = data.get("stateHandle")
    if not new_handle:
        fail("No stateHandle in identify response")
    print("[DEV][INFO] Identity accepted.")
    return new_handle


async def challenge_answer(session: aiohttp.ClientSession, passcode: str, state_handle: str) -> str:
    """POST /idp/idx/challenge/answer with password → returns successWithInteractionCode."""
    print("[DEV][INFO] Submitting password...")
    async with session.post(
        f"{OKTA_BASE}/idp/idx/challenge/answer",
        json={"credentials": {"passcode": passcode}, "stateHandle": state_handle},
        headers=JSON_HEADERS,
    ) as resp:
        if resp.status != 200:
            fail(f"challenge/answer failed with status {resp.status}")
        data = await resp.json(content_type=None)

    # Response contains successWithInteractionCode.value which we follow
    success = data.get("successWithInteractionCode", {})
    href = success.get("href") or success.get("value", {}).get("href")
    if not href:
        # Try nested structure
        for item in data.get("remediation", {}).get("value", []):
            if item.get("name") == "issue":
                href = item.get("href")
                break
    if not href:
        fail(f"No redirect href after challenge/answer. Keys: {list(data.keys())}")
    print("[DEV][INFO] Password accepted, got callback href.")
    return href


async def exchange_code(session: aiohttp.ClientSession, href: str) -> None:
    """Follow the successWithInteractionCode href to complete OAuth and land on developer.servicenow.com."""
    print("[DEV][INFO] Exchanging interaction code, completing login...")
    async with session.get(href, allow_redirects=True, max_redirects=15) as resp:
        final_url = str(resp.url)
        status = resp.status

    if "developer.servicenow.com" not in final_url:
        fail(f"Did not land on developer.servicenow.com after code exchange. Got: {final_url} (status {status})")
    print(f"[DEV][INFO] Landed on: {final_url}")


async def touch_dev_portal(session: aiohttp.ClientSession) -> None:
    """Call the two keepalive endpoints on developer.servicenow.com."""
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
        print(f"[DEV][INFO] check_instance_awake → {resp.status}")

    print("[DEV][INFO] Calling touch-session...")
    async with session.get(
        f"{DEV_BASE}/api/now/uisession/touch-session",
        headers=dev_headers,
    ) as resp:
        print(f"[DEV][INFO] touch-session → {resp.status}")


async def run():
    if not all([DEV_USER, DEV_PASS]):
        fail("Missing DEV_USER or DEV_PASS env vars.")

    connector = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        state_token = await get_state_token(session)
        state_handle = await introspect(session, state_token)
        state_handle = await identify(session, DEV_USER, state_handle)
        href = await challenge_answer(session, DEV_PASS, state_handle)
        await exchange_code(session, href)
        await touch_dev_portal(session)

    print("[DEV][SUCCESS] Developer portal keep-alive complete.")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
