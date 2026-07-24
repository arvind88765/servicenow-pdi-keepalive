# 🔋 PDI Keep-Alive

Never let your ServiceNow PDI hibernate again. Fork it, add your secrets, done. Fully automated, zero maintenance, zero cost.

## the problem

Free tier PDIs sleep after a few days of no activity, and waking one back up can take forever. This repo keeps your PDI alive using **two independent methods** running concurrently every day via GitHub Actions — so even if one fails, the other has you covered.

## two methods, one run

| | Method 1 | Method 2 |
|---|---|---|
| **What it does** | Logs into your PDI directly via headless browser | Logs into developer.servicenow.com via async HTTP (no browser) |
| **How** | Playwright + Chromium | aiohttp + Okta IDX API |
| **Speed** | ~30s (browser startup) | ~3-5s (pure HTTP) |
| **Secrets needed** | `PDI_URL` `PDI_USER` `PDI_PASS` | `DEV_USER` `DEV_PASS` |
| **Proof** | 5 screenshots saved as artifacts | Console logs |

Both methods run **at the same time** in a single workflow run. You can use either one or both — if you only set one set of secrets, only that method runs.

## how it works

**Method 1 — PDI browser login:**
Opens your PDI URL in a headless Chromium browser, fills in username/password, clicks login. Resets the PDI's activity timer directly. Takes 5 screenshots as proof.

**Method 2 — Dev portal HTTP login:**
Logs into `developer.servicenow.com` using the Okta IDX REST API (the same flow your browser does, but without a browser). After login, calls `check_instance_awake` and `touch-session` on the dev portal to reset the activity timer from the ServiceNow developer side.

Having both means: if your PDI URL changes, or the browser login breaks, Method 2 still keeps the instance alive from the developer portal side — and vice versa.

## setup

### if you want BOTH methods (recommended)

1. **Fork this repo.**

2. Go to **Settings > Secrets and variables > Actions** in your fork and add these 5 secrets:

   | Secret | Value |
   |---|---|
   | `PDI_URL` | your PDI URL, like `https://dev12345.service-now.com` |
   | `PDI_USER` | your PDI username |
   | `PDI_PASS` | your PDI password |
   | `DEV_USER` | your developer.servicenow.com email (same account you use to log into the dev portal) |
   | `DEV_PASS` | your developer.servicenow.com password |

3. Go to your fork's **Actions** tab, enable workflows if it asks.

4. Click **Run workflow** on "PDI Keep-Alive" to test it right now.

### if you only want Method 1 (PDI browser login)

Only add `PDI_URL`, `PDI_USER`, `PDI_PASS`. Method 2 is automatically skipped.

### if you only want Method 2 (dev portal HTTP login)

Only add `DEV_USER`, `DEV_PASS`. Method 1 is automatically skipped (no Playwright needed).

## how to check it actually worked

Every run saves 5 screenshots from Method 1. Here's how to find them:

1. Go to your fork's [**latest workflow runs**](../../actions/workflows/keepalive.yml)
2. Click into the latest run
3. Scroll down to **Artifacts** at the bottom
4. Download **keepalive-proof-X** (zip), unzip it:
   - `1_initial_page.png` — what it saw when it opened your PDI
   - `2_after_wake_attempt.png` — after trying to wake it up if it was hibernating
   - `3_form_filled.png` — login form right before submit
   - `4_after_submit.png` — right after clicking login
   - `5_final_landed_page.png` — the logged-in page (proof it worked)

Also check the logs: expand "Run keep-alive (both methods)" and look for:
- `[Method 1 PDI]      SUCCESS`
- `[Method 2 Dev Portal] SUCCESS`

Artifacts auto-delete after 3 days.

## run locally

```bash
cp .env.example .env   # fill in your real values
pip install -r requirements.txt
playwright install chromium

# run both methods
export $(cat .env | xargs) && python main.py

# or run Method 2 only (no browser needed)
export DEV_USER=you@email.com DEV_PASS=yourpass && python keepalive_dev.py

# or run Method 1 only
export PDI_URL=https://devXXXX.service-now.com PDI_USER=admin PDI_PASS=pass && python keepalive.py
```

## heads up

- MFA on your PDI? Method 1 won't work — disable MFA on the dev instance. Method 2 (dev portal) also won't work if MFA is enabled on your ServiceNow developer account.
- `DEV_USER`/`DEV_PASS` are the credentials for `developer.servicenow.com`, not your PDI instance — they're usually your personal ServiceNow account (the one you used to register for a PDI).
- Want it to run more/less often? Edit the `cron` line in `.github/workflows/keepalive.yml`.
- This just automates normal logins — nothing sketchy, no bypassing anything.
- Pro tip: don't use your main admin creds if you can avoid it, create a low-priv user just for keepalive.

## why other keep-alive scripts break

Most PDI keep-alive scripts do a raw `requests.post()` straight to `/login.do` with guessed selectors and no CSRF token. That fails silently because ServiceNow's login form needs a `sysparm_ck` token first, and guessed field names break the moment ServiceNow updates their page.

This repo is different:
- **Method 1** uses a real browser — actual login flow, verified against a real PDI, takes screenshots so you can see exactly what happened
- **Method 2** uses the real Okta IDX REST API that the browser itself uses — extracted from actual network traffic, not guessed
- Both fail loudly with a non-zero exit code — GitHub Actions marks the run as failed so you get notified
- Your credentials live in your own fork's encrypted secrets — nobody else ever sees them

## credits

Built out of frustration with losing PDIs mid-project. If it saved you a headache, a ⭐ means a lot and helps other devs find it.

PRs welcome — this is meant to be a community tool.

## disclaimer

This is a personal educational project that automates the same login you'd do by hand in a browser. Nothing here bypasses security or does anything ServiceNow wouldn't want a legitimate developer doing. Use responsibly, don't spam it, and only use it on instances that are yours.
