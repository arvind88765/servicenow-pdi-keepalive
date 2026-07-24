# 🔋 PDI Keep-Alive

Tired of your ServiceNow PDI hibernating mid-project? This repo fixes that. Fork it, add your secrets, forget about it. Runs every day automatically, zero cost, zero maintenance.

## Why Your PDI Keeps Dying

Free-tier PDIs go to sleep after a few days of no activity. Waking them back up is painfully slow. This repo logs into your instance every day so the timer never resets.

## Two Methods (Use Both for Max Reliability)

This repo runs **two completely independent keep-alive methods at the same time**. If one fails for any reason, the other still keeps your PDI alive.

### Method 1 — PDI Direct Login

Opens a headless browser, navigates to your PDI URL, logs in with your credentials, and lands on the dashboard. That login resets the activity timer directly on the instance itself.

### Method 2 — Dev Portal Wakeup (Recommended, More Reliable)

Logs into developer.servicenow.com through the full Okta SSO flow, then calls the exact same backend APIs that fire when you click the "Wake instance" button on the dev portal. This includes `check_instance_awake`, `instanceInfo`, `instance.hibernate.wake_up`, and `touch-session`.

**Why Method 2 is the better option:**

Method 1 depends on your PDI being reachable. If the instance is deep in hibernation or there's a ServiceNow infrastructure issue, the browser times out and Method 1 fails. Method 2 hits the dev portal side instead, which stays up even when the PDI itself is struggling to wake. It's the same thing you'd do manually when you open the dev portal and click "Wake instance," except automated.

If you can only set up one method, go with Method 2.

| | Method 1 | Method 2 |
|---|---|---|
| What it does | Logs into your PDI directly | Logs into developer.servicenow.com and triggers wake APIs |
| How | Playwright headless Chromium | Playwright + aiohttp |
| Reliability | Depends on PDI being reachable | Works even when PDI is hibernating |
| Proof | 5 screenshots | 4 screenshots |
| Secrets needed | `PDI_URL`, `PDI_USER`, `PDI_PASS` | `DEV_USER`, `DEV_PASS` |

## Setup (5 min)

1. **Fork this repo** (top right, Fork button)

2. **Add your secrets** — go to **Settings → Secrets and variables → Actions → New repository secret** in your fork.

   If you want both methods (strongly recommended):

   | Secret | What to put |
   |---|---|
   | `PDI_URL` | Your PDI URL, like `https://dev12345.service-now.com` |
   | `PDI_USER` | Your PDI username |
   | `PDI_PASS` | Your PDI password |
   | `DEV_USER` | Your developer.servicenow.com email (the account you used to sign up for a PDI) |
   | `DEV_PASS` | Your developer.servicenow.com password |

   - Only want Method 2? Just add `DEV_USER` and `DEV_PASS` — Method 1 gets skipped automatically.
   - Only want Method 1? Just add `PDI_URL`, `PDI_USER`, `PDI_PASS` — Method 2 gets skipped automatically.

3. Go to your fork's **Actions** tab and enable workflows if it asks.

4. Hit **Run workflow** to test it right now.

Done. It runs itself every day at 6am UTC, forever.

## Proof It Actually Worked

Every run saves screenshots so you can see exactly what happened. No blind trust needed.

**Method 1 screenshots** (`proof/` folder):
- `1_initial_page.png` — what it saw when it first opened your PDI
- `2_after_wake_attempt.png` — after trying to wake the instance
- `3_form_filled.png` — login form right before submit
- `4_after_submit.png` — after clicking login
- `5_final_landed_page.png` — the logged-in dashboard

**Method 2 screenshots** (`proof_dev/` folder):
- `1_login_page.png` — the Okta SSO login form
- `2_form_filled.png` — credentials filled in before submit
- `3_after_submit.png` — right after clicking Sign In
- `4_dev_portal_landed.png` — logged into developer.servicenow.com

To find them: **Actions tab → click the latest run → scroll down to Artifacts → download the zip.**

Also check the run logs. Expand "Run keep-alive (both methods)" and look for:
```
[Method 1 PDI]        SUCCESS
[Method 2 Dev Portal] SUCCESS
```

Screenshots auto-delete after 3 days, so download the zip if you want to keep them.

## Run Locally

```bash
cp .env.example .env
# fill in your real values

pip install -r requirements.txt
playwright install chromium

# run both methods at once
export $(cat .env | xargs) && python main.py

# run only Method 2 (recommended, no PDI credentials needed)
export DEV_USER=you@email.com DEV_PASS=yourpass && python keepalive_dev.py

# run only Method 1
export PDI_URL=https://devXXXX.service-now.com PDI_USER=admin PDI_PASS=pass && python keepalive.py
```

## Good to Know

- **MFA on your account?** Neither method will work. Disable MFA on your PDI and on your developer.servicenow.com account first.
- `DEV_USER` and `DEV_PASS` are your developer.servicenow.com credentials, **not** your PDI credentials — it's the personal account you used when you registered for a free PDI.
- Want it to run more or less often? Edit the cron line in `.github/workflows/keepalive.yml`.
- Don't use your main admin credentials if you can avoid it — spin up a low-priv user just for this.

## Why Most Other Keep-Alive Scripts Break

Most scripts out there just do a raw POST to `/login.do` with hardcoded field names. ServiceNow requires a `sysparm_ck` CSRF token embedded in the page before it accepts a login, so those scripts fail silently and you don't find out until your PDI is already dead.

This repo is different:

- **Method 1** uses a real headless browser so the complete page lifecycle runs exactly like a human would do it.
- **Method 2** uses the actual Okta SSO flow that developer.servicenow.com uses internally, extracted from real network traffic. It calls the same wake APIs the dev portal UI calls when you click "Wake Instance."

Both methods fail loudly with a non-zero exit code so GitHub marks the run red and you get notified immediately.

Your credentials live in your own fork's encrypted secrets and never touch anyone else's server.

## Credits

Built because losing PDIs mid-project is genuinely annoying. If it saved you, a star on the repo would be sick and helps other devs find it.

PRs welcome — this is meant to be a community thing.

## Disclaimer

This automates a completely normal login, the same one you do by hand in a browser. Nothing here bypasses any security or does anything ServiceNow wouldn't want a legit developer doing. Use it on your own instances only, don't spam it.
