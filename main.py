import asyncio
import os
import sys
import subprocess


def run_pdi():
    """Run Method 1 (Playwright PDI login) in a subprocess."""
    result = subprocess.run(
        [sys.executable, "keepalive.py"],
        capture_output=True,
        text=True,
    )
    return result


async def run_dev():
    """Run Method 2 (aiohttp dev portal login) inline."""
    from keepalive_dev import run as dev_run
    await dev_run()


async def main():
    pdi_enabled = all([
        os.environ.get("PDI_URL"),
        os.environ.get("PDI_USER"),
        os.environ.get("PDI_PASS"),
    ])
    dev_enabled = all([
        os.environ.get("DEV_USER"),
        os.environ.get("DEV_PASS"),
    ])

    if not pdi_enabled and not dev_enabled:
        print("[ERROR] No credentials configured. Set PDI_URL/PDI_USER/PDI_PASS for Method 1 "
              "and/or DEV_USER/DEV_PASS for Method 2.")
        sys.exit(1)

    tasks = []

    if pdi_enabled:
        print("[INFO] Method 1 (PDI browser login) → enabled")
        # Run in thread so it doesn't block the event loop
        loop = asyncio.get_event_loop()
        tasks.append(loop.run_in_executor(None, run_pdi))
    else:
        print("[INFO] Method 1 (PDI browser login) → skipped (PDI_URL/PDI_USER/PDI_PASS not set)")

    if dev_enabled:
        print("[INFO] Method 2 (Dev portal aiohttp login) → enabled")
        tasks.append(asyncio.create_task(run_dev()))
    else:
        print("[INFO] Method 2 (Dev portal aiohttp login) → skipped (DEV_USER/DEV_PASS not set)")

    print("[INFO] Running enabled methods concurrently...\n")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    pdi_result = None
    dev_result = None

    idx = 0
    if pdi_enabled:
        pdi_result = results[idx]
        idx += 1
    if dev_enabled:
        dev_result = results[idx]

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)

    overall_ok = True

    if pdi_enabled:
        if isinstance(pdi_result, Exception):
            print(f"[Method 1 PDI]      FAIL — {pdi_result}")
            overall_ok = False
        elif pdi_result.returncode != 0:
            print(f"[Method 1 PDI]      FAIL (exit {pdi_result.returncode})")
            print(pdi_result.stdout[-500:] if pdi_result.stdout else "")
            print(pdi_result.stderr[-200:] if pdi_result.stderr else "")
            overall_ok = False
        else:
            print("[Method 1 PDI]      SUCCESS")

    if dev_enabled:
        if isinstance(dev_result, Exception):
            print(f"[Method 2 Dev Portal] FAIL — {dev_result}")
            overall_ok = False
        else:
            print("[Method 2 Dev Portal] SUCCESS")

    print("=" * 50)

    if not overall_ok:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
