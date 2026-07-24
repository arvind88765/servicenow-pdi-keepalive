# 🔋 PDI Keep-Alive

tired of your ServiceNow PDI hibernating mid-project? this repo fixes that. fork it, add your secrets, forget about it. runs every day automatically, zero cost, zero maintenance.

## why your PDI keeps dying

free tier PDIs go to sleep after a few days of no activity. waking them back up is painfully slow. this repo logs into your instance every day so the timer never resets.

## two methods (use both for max reliability)

this repo runs **two completely independent keepalive methods at the same time**. if one fails for any reason, the other still keeps your PDI alive.

### Method 1 ———— PDI direct login

opens a headless browser, navigates to your PDI URL, logs in with your credentials, lands on the dashboard. that login resets the activity timer directly on the instance itself.

### Method 2 ———— Dev portal wakeup (recommended, more reliable)

logs into developer.servicenow.com through the full Okta SSO flow, then calls the exact same backend APIs that fire when you click the "Wake instance" button on the dev portal. this includes `check_instance_awake`, `instanceInfo`, `instance.hibernate.wake_up`, and `touch-session`.

**why Method 2 is the better option:**

Method 1 depends on your PDI being reachable. if the instance is deep in hibernation or there's a ServiceNow infrastructure issue, the browser times out and Method 1 fails. Method 2 hits the dev portal side instead, which stays up even when the PDI itself is struggling to wake. it's the same thing you'd do manually when you open the dev portal and click Wake instance, except automated.

if you can only set up one method, go with Method 2.

| | Method 1 | Method 2 |
|---|---|---|
| what it does | logs into your PDI directly | logs into developer.servicenow.com and triggers wake APIs |
| how | Playwright headless Chromium | Playwright + aiohttp |
| reliability | depends on PDI being reachable | works even when PDI is hibernating |
| proof | 5 screenshots | 4 screenshots |
| secrets needed | PDI_URL, PDI_USER, PDI_PASS | DEV_USER, DEV_PASS |

## setup (5 min)

**1. fork this repo** (top right, Fork button)

**2. add your secrets** — go to Settings > Secrets and variables > Actions > New repository secret in your fork

if you want both methods (strongly recommended):

| Secret | What to put |
|---|---|
| PDI_URL | your PDI url like `https://dev12345.service-now.com` |
| PDI_USER | your PDI username |
| PDI_PASS | your PDI password |
| DEV_USER | your developer.servicenow.com email (the account you used to sign up for a PDI) |
| DEV_PASS | your developer.servicenow.com password |

only want Method 2? just add DEV_USER and DEV_PASS. Method 1 gets skipped automatically.

only want Method 1? just add PDI_URL, PDI_USER, PDI_PASS. Method 2 gets skipped automatically.

**3.** go to your fork's Actions tab and enable workflows if it asks

**4.** hit Run workflow to test it right now

done. it runs itself every day at 6am UTC forever.

## proof it actually worked

every run saves screenshots so you can see exactly what happened. no blind trust needed.

**Method 1 screenshots (proof folder):**
- `1_initial_page.png` what it saw when it first opened your PDI
- `2_after_wake_attempt.png` after trying to wake the instance
- `3_form_filled.png` login form right before submit
- `4_after_submit.png` after clicking login
- `5_final_landed_page.png` the logged in dashboard

**Method 2 screenshots (proof_dev folder):**
- `1_login_page.png` the Okta SSO login form
- `2_form_filled.png` credentials filled in before submit
- `3_after_submit.png` right after clicking Sign In
- `4_dev_portal_landed.png` logged into developer.servicenow.com

to find them: Actions tab > click the latest run > scroll down to Artifacts > download the zip.

also check the run logs. expand "Run keep-alive (both methods)" and look for:
```
[Method 1 PDI]        SUCCESS
[Method 2 Dev Portal] SUCCESS
```

screenshots auto delete after 3 days so download the zip if you want to keep them.

## run locally

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

## good to know

MFA on your account? neither method will work. disable MFA on your PDI and on your developer.servicenow.com account first.

DEV_USER and DEV_PASS are your developer.servicenow.com credentials, not your PDI credentials. it's the personal account you used when you registered for a free PDI.

want it to run more or less often? edit the cron line in `.github/workflows/keepalive.yml`.

don't use your main admin credentials if you can avoid it. spin up a low-priv user just for this.

## why most other keepalive scripts break

most scripts out there just do a raw POST to `/login.do` with hardcoded field names. ServiceNow requires a `sysparm_ck` CSRF token embedded in the page before it accepts a login, so those scripts fail silently and you don't find out until your PDI is already dead.

this repo is different:

Method 1 uses a real headless browser so the complete page lifecycle runs exactly like a human would do it.

Method 2 uses the actual Okta SSO flow that developer.servicenow.com uses internally, extracted from real network traffic. it calls the same wake APIs the dev portal UI calls when you click Wake Instance.

both methods fail loudly with a non-zero exit code so GitHub marks the run red and you get notified immediately.

your credentials live in your own fork's encrypted secrets and never touch anyone else's server.

## credits

built because losing PDIs mid-project is genuinely annoying. if it saved you, a star on the repo would be sick and helps other devs find it.

PRs welcome, this is meant to be a community thing.

## disclaimer

this automates a completely normal login, the same one you do by hand in a browser. nothing here bypasses any security or does anything ServiceNow wouldn't want a legit developer doing. use it on your own instances only, don't spam it.
