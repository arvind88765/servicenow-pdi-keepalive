# 🔋 PDI Keep-Alive

your PDI will never hibernate again. fork it, drop in your secrets, and forget about it. free, automated, no server needed.

## the problem

free tier PDIs go to sleep after a few days of no activity. waking them back up takes forever and kills your flow. this repo fixes that by running two keepalive methods every single day on GitHub Actions so your instance stays alive no matter what.

## two methods, both run at the same time

**Method 1** logs straight into your PDI via a headless browser and resets the activity timer on the instance itself.

**Method 2** logs into developer.servicenow.com (the dev portal, not the PDI directly) using the same Okta SSO flow your browser uses, then calls the portal's wakeup APIs to keep things alive from the ServiceNow side too.

both run concurrently in one workflow run. if one fails, the other still saves you. you can use either one or both depending on what secrets you set.

| | Method 1 | Method 2 |
|---|---|---|
| logs into | your PDI directly | developer.servicenow.com |
| how | Playwright headless browser | aiohttp async HTTP (no browser) |
| speed | ~30s | ~5s |
| proof | 5 screenshots | 3 screenshots |
| secrets needed | PDI_URL, PDI_USER, PDI_PASS | DEV_USER, DEV_PASS |

## setup (literally 5 min)

**1. fork this repo** (top right, hit Fork)

**2. add your secrets** — go to Settings > Secrets and variables > Actions > New repository secret in your fork

if you want both methods (recommended):

| Secret | What to put |
|---|---|
| PDI_URL | your PDI url like `https://dev12345.service-now.com` |
| PDI_USER | your PDI username |
| PDI_PASS | your PDI password |
| DEV_USER | your developer.servicenow.com email (the account you used to register for a PDI) |
| DEV_PASS | your developer.servicenow.com password |

if you only want Method 1, just add PDI_URL + PDI_USER + PDI_PASS.

if you only want Method 2, just add DEV_USER + DEV_PASS. Playwright wont even install, faster run.

**3.** go to your fork's **Actions** tab and enable workflows if it asks

**4.** click **Run workflow** on "PDI Keep-Alive" to test it right now instead of waiting for tomorrow

done. it runs itself every day at 6am UTC forever.

## checking if it worked

every run saves screenshots showing exactly what happened.

**Method 1 screenshots (proof folder):**
- `1_initial_page.png` what it saw when it first opened your PDI
- `2_after_wake_attempt.png` after trying to wake it if it was hibernating
- `3_form_filled.png` login form right before hitting submit
- `4_after_submit.png` right after clicking login
- `5_final_landed_page.png` the actual logged in page, this is your proof

**Method 2 screenshots (proof_dev folder):**
- `1_dev_portal_home.png` dev portal right after session cookies were injected
- `2_dev_portal_loaded.png` after page fully loaded
- `3_dev_portal_final.png` final state confirming login worked

to find them: go to your fork's Actions tab > click the latest run > scroll down to Artifacts > download the zip.

if something went wrong youll see a `_failed.png` instead of the final one. open it to see what happened.

screenshots auto delete after 3 days. download the zip if you want to keep them.

also check the logs inside the run. expand "Run keep-alive (both methods)" and look for:
```
[Method 1 PDI]        SUCCESS
[Method 2 Dev Portal] SUCCESS
```

## run it locally

```bash
cp .env.example .env
# fill in .env with your real values

pip install -r requirements.txt
playwright install chromium

# run both at once
export $(cat .env | xargs) && python main.py

# only Method 2 (fast, no browser)
export DEV_USER=you@email.com DEV_PASS=yourpass && python keepalive_dev.py

# only Method 1
export PDI_URL=https://devXXXX.service-now.com PDI_USER=admin PDI_PASS=pass && python keepalive.py
```

## things worth knowing

MFA enabled on your PDI? Method 1 wont work, you need to disable MFA on the dev instance for browser login to work. same goes for Method 2 if MFA is on your developer.servicenow.com account.

DEV_USER and DEV_PASS are your developer.servicenow.com credentials, not your PDI credentials. its the account you used when you signed up for a free PDI at developer.servicenow.com.

want it to run more or less often? edit the cron line in `.github/workflows/keepalive.yml`.

pro tip: spin up a dedicated low-priv login just for this instead of using your main admin account.

## why most other keepalive scripts dont work

most scripts out there just do a raw POST to `/login.do` with hardcoded field names and no CSRF token. ServiceNow requires a `sysparm_ck` token embedded in the page before it accepts a login POST, so those scripts fail silently half the time and you dont find out until your PDI is already dead.

this repo actually uses the real login flows:
- Method 1 uses a real headless browser so the full page lifecycle runs exactly like a human would do it
- Method 2 uses the actual Okta IDX REST API that developer.servicenow.com uses internally, not guessed selectors
- both fail loudly with a non-zero exit code so GitHub marks the run red and you get notified
- your creds live in your own fork's encrypted secrets and never touch anyone else's server

## credits

built this because I kept losing PDIs mid-project and it was genuinely annoying. if it saved you from a hibernation headache, a star on the repo would be sick and helps other devs find it.

PRs welcome, this is meant to be a community thing not a solo project.

## disclaimer

this just automates a normal login, the same one you do by hand in a browser. nothing here bypasses any security or does anything ServiceNow wouldnt want a legit developer doing. use it on your own instances only, dont spam it.
