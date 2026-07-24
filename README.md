# 🔋 PDI Keep-Alive

your PDI will never hibernate again. fork it, drop in your secrets, hit run. free, no server needed.

## the problem

free tier PDIs go to sleep after a few days of no activity. waking them back up takes forever. this repo keeps your PDI alive using two independent methods so even if one fails, the other saves you.

## two methods, both run at the same time

**Method 1** opens a headless browser, logs straight into your PDI, and resets the activity timer directly on the instance.

**Method 2** logs into developer.servicenow.com via the Okta SSO flow, then calls the portal's wakeup APIs — same thing that happens when you click "Wake instance" on the dev portal.

both run concurrently. if one fails, the other still works.

| | Method 1 | Method 2 |
|---|---|---|
| logs into | your PDI directly | developer.servicenow.com |
| how | Playwright headless browser | Playwright + aiohttp |
| proof | 5 screenshots | 4 screenshots |
| secrets needed | PDI_URL, PDI_USER, PDI_PASS | DEV_USER, DEV_PASS |

## setup

**1. fork this repo**

**2. add your secrets** — Settings > Secrets and variables > Actions > New repository secret

| Secret | What to put |
|---|---|
| PDI_URL | your PDI url like `https://dev12345.service-now.com` |
| PDI_USER | your PDI username |
| PDI_PASS | your PDI password |
| DEV_USER | your developer.servicenow.com email |
| DEV_PASS | your developer.servicenow.com password |

only want Method 1? just add PDI_URL + PDI_USER + PDI_PASS.
only want Method 2? just add DEV_USER + DEV_PASS.

**3.** go to Actions tab, enable workflows

**4.** click **Run workflow** whenever you want to run it

the workflow is manual trigger only — no automatic schedule. run it yourself whenever you need it.

## how to check if it worked

every run saves screenshots proving what happened.

**Method 1 screenshots (proof folder):**
- `1_initial_page.png` what it saw when it opened your PDI
- `2_after_wake_attempt.png` after trying to wake it
- `3_form_filled.png` login form before submit
- `4_after_submit.png` right after clicking login
- `5_final_landed_page.png` the logged in page

**Method 2 screenshots (proof_dev folder):**
- `1_login_page.png` the Okta login form
- `2_form_filled.png` after filling credentials
- `3_after_submit.png` after clicking Sign In
- `4_dev_portal_landed.png` logged into developer.servicenow.com

to find them: Actions tab > click the run > scroll down to Artifacts > download the zip.

check the logs too — look for:
```
[Method 1 PDI]        SUCCESS
[Method 2 Dev Portal] SUCCESS
```

## run locally

```bash
cp .env.example .env
# fill in your real values

pip install -r requirements.txt
playwright install chromium

# run both methods
export $(cat .env | xargs) && python main.py

# only Method 2
export DEV_USER=you@email.com DEV_PASS=yourpass && python keepalive_dev.py

# only Method 1
export PDI_URL=https://devXXXX.service-now.com PDI_USER=admin PDI_PASS=pass && python keepalive.py
```

## how Method 2 works under the hood

1. Playwright opens `developer.servicenow.com/userlogin.do`
2. follows the SAML redirect chain to `signon.servicenow.com`
3. fills `#username` → clicks Next → fills `#password` → clicks Sign In
4. lands on `developer.servicenow.com/dev.do`
5. aiohttp uses the browser session cookies to call:
   - `check_instance_awake`
   - `instanceInfo?direct_wake_up=true`
   - `devportal.do?action=instance.hibernate.wake_up` (same as clicking the Wake Instance button)
   - `touch-session`

## things to know

MFA on your account? neither method will work — disable MFA on your PDI and developer.servicenow.com account.

DEV_USER and DEV_PASS are your developer.servicenow.com credentials (the account you used to register for a PDI), not your PDI credentials.

if the PDI is down due to a ServiceNow infrastructure issue, Method 1 will fail regardless — thats a ServiceNow side problem, not the script.

## credits

built because losing PDIs mid-project is genuinely annoying. if it helped, a star on the repo is appreciated.

PRs welcome.

## disclaimer

this automates a normal login, same as what you do manually in a browser. nothing here bypasses security. use it on your own instances only.
