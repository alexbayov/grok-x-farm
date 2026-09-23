#!/usr/bin/env python3
"""grok_reg_v2.py — Fixed patchright registration with screenshots."""
import asyncio, json, os, random, string, time, urllib.request, urllib.parse, re, sys, base64

DUCKMAIL_API = "https://api.duckmail.sbs"
XAI_SIGNUP = "https://accounts.x.ai/sign-up?redirect=grok-com"
GATEWAY = os.getenv("G2A_BASE", "http://127.0.0.1:8000")
ADMIN_PASS = os.getenv("G2A_ADMIN_PASS", "iRaFzoZ2c20Nur")
OUT_DIR = "/root/grok-x-farm/screenshots"
os.makedirs(OUT_DIR, exist_ok=True)

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def http_post(url, data, headers=None):
    h = {"Content-Type": "application/json"}
    if headers: h.update(headers)
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def get_domains():
    d = http_get(f"{DUCKMAIL_API}/domains")
    if isinstance(d, list) and d and isinstance(d[0], str): return d
    if isinstance(d, dict) and "hydra:member" in d: d = d["hydra:member"]
    return [x.get("domain","") if isinstance(x, dict) else str(x) for x in d if x]

def create_email(email_addr):
    return http_post(f"{DUCKMAIL_API}/accounts", {"address": email_addr, "password": "P@ssw0rd123!", "expiresIn": 0})

def get_token(email_addr):
    data = urllib.parse.urlencode({"address": email_addr, "password": "P@ssw0rd123!"}).encode()
    req = urllib.request.Request(f"{DUCKMAIL_API}/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("token","")
    except: return ""

def get_messages(token):
    return http_get(f"{DUCKMAIL_API}/messages", {"Authorization": f"Bearer {token}"})

def wait_for_code(email_addr, timeout=90):
    token = get_token(email_addr)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            token = get_token(email_addr)
            msgs = get_messages(token)
            for msg in msgs:
                recipients = [t.get("address","").lower() for t in (msg.get("to") or [])]
                if email_addr.lower() not in recipients: continue
                text = str(msg.get("subject","")) + " " + str(msg.get("text","")) + " " + str(msg.get("html",""))
                m = re.search(r'\b(\d{3}[-\s]?\d{3})\b', text)
                if m: return m.group(1).replace(" ", "-")
        except: pass
        time.sleep(3)
    return None

def import_sso(sso_token):
    data = json.dumps({"username":"admin","password":ADMIN_PASS}).encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/auth/login", data=data,
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read())["data"]["tokens"]["accessToken"]
    boundary = "----" + "".join(random.choices(string.ascii_lowercase, k=12))
    mp = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sso.txt\"\r\n"
          f"Content-Type: text/plain\r\n\r\n{sso_token}\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/accounts/web/import", data=mp,
                                 headers={"Authorization":f"Bearer {tok}",
                                          "Content-Type":f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
    m = re.search(r'"created":(\d+).*?"synced":(\d+)', body)
    return m.groups() if m else ("?","?")

async def register():
    from patchright.async_api import async_playwright

    # Create email
    domains = get_domains()
    domain = random.choice(domains) if domains else "niceground.shop"
    username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@{domain}"
    print(f"[1] Creating email: {email}")
    create_email(email)
    print(f"[+] Email created")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--window-size=1920,1080"]
        )
        context = await browser.new_context(
            viewport={"width":1920,"height":1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Open signup
        print("[2] Opening x.ai signup...")
        await page.goto(XAI_SIGNUP, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=f"{OUT_DIR}/01_signup.png")
        print(f"[*] Screenshot: 01_signup.png")

        # FIRST: dismiss cookie consent banner — it blocks interaction
        print("[2a] Dismissing cookie banner...")
        try:
            accept = page.locator("button:has-text('Accept All Cookies')")
            if await accept.count() > 0 and await accept.first.is_visible():
                await accept.first.click()
                print("[+] Clicked 'Accept All Cookies'")
                await page.wait_for_timeout(1000)
        except: pass
        try:
            reject = page.locator("button:has-text('Reject All')")
            if await reject.count() > 0 and await reject.first.is_visible():
                await reject.first.click()
                print("[+] Clicked 'Reject All'")
                await page.wait_for_timeout(1000)
        except: pass
        # Also try clicking the X close button on the cookie banner
        try:
            close = page.locator('[aria-label="Close"], .ot-close, #onetrust-close-btn-container button')
            if await close.count() > 0:
                await close.first.click()
                print("[+] Closed cookie banner via X")
                await page.wait_for_timeout(1000)
        except: pass

        # Find all buttons
        btns = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button'))
                .slice(0,15)
                .map(e => ({text: (e.textContent||'').trim().substring(0,60), visible: e.offsetParent !== null}))
                .filter(x => x.visible);
        }""")
        print(f"[*] Visible buttons: {json.dumps(btns, indent=2)}")

        # Click "Sign up with email" — use Playwright's real mouse click, NOT JS .click()
        print("[3] Clicking 'Sign up with email' via Playwright locator...")
        email_btn = page.locator("button:has-text('Sign up with email')").first
        await email_btn.click()
        await page.wait_for_timeout(3000)
        await page.screenshot(path=f"{OUT_DIR}/02_after_click.png")
        print(f"[*] Screenshot: 02_after_click.png")
        print(f"[*] URL: {page.url}")
        print(f"[*] Page title: {await page.title()}")

        # Look for email input
        print("[4] Looking for email input...")
        email_sel = 'input[data-testid="email"], input[name="email"], input[type="email"]'
        try:
            email_loc = page.locator(email_sel).first
            await email_loc.wait_for(state="visible", timeout=10000)
            print(f"[+] Email input visible!")
            await email_loc.click()
            await page.wait_for_timeout(300)
            # Use type() not fill() — React controlled inputs lose chars with fill()
            await email_loc.type(email, delay=50)
            await page.wait_for_timeout(800)
            actual = await email_loc.input_value()
            print(f"[*] Filled: {actual}")
            # Verify exact match
            if actual != email:
                print(f"[!] Email mismatch! Expected: {email}, Got: {actual}")
                # Try again character by character
                await email_loc.click()
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Backspace")
                await page.wait_for_timeout(200)
                await email_loc.type(email, delay=80)
                await page.wait_for_timeout(800)
                actual = await email_loc.input_value()
                print(f"[*] After retry: {actual}")
        except Exception as e:
            print(f"[-] No email input found: {e}")
            # Try evaluating page for inputs
            inputs = await page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(i => ({type:i.type, name:i.name, placeholder:i.placeholder||'', visible:i.offsetParent!==null})).slice(0,10)""")
            print(f"[*] All inputs: {inputs}")
            await browser.close()
            return None

        # Press Enter to submit
        print("[5] Submitting form...")
        # Use Playwright locator to click "Sign up" button
        signup_btn = page.locator("button:has-text('Sign up'):not(:has-text('email')):not(:has-text('Go back')):not(:has-text('Apple')):not(:has-text('Google')):not(:has-text('GitHub')):not(:has-text('with X'))").first
        if await signup_btn.count() > 0:
            is_visible = await signup_btn.is_visible()
            is_enabled = await signup_btn.is_enabled()
            txt = await signup_btn.text_content()
            print(f"[*] Found button: '{txt.strip()}' visible={is_visible} enabled={is_enabled}")
            if is_enabled:
                await signup_btn.click()
                print("[+] Clicked 'Sign up' button")
            else:
                print("[-] Button disabled — email may be invalid or not accepted")
                # Try Enter anyway
                email_loc = page.locator(email_sel).first
                await email_loc.press("Enter")
                print("[*] Tried Enter instead")
        else:
            print("[-] No 'Sign up' button found")
            await email_loc.press("Enter")
        
        await page.wait_for_timeout(3000)
        print(f"[*] After submit, URL: {page.url}")
        await page.screenshot(path=f"{OUT_DIR}/03_after_submit.png")

        # Wait for verification code
        print("[6] Waiting for verification code...")
        code = wait_for_code(email, timeout=90)
        if not code:
            print("[-] No code received")
            await page.screenshot(path=f"{OUT_DIR}/04_no_code.png")
            await browser.close()
            return None
        print(f"[+] Code: {code}")

        # Fill code
        print("[7] Filling verification code...")
        await page.wait_for_timeout(1000)
        code_inputs = page.locator('input[type="text"]:visible, input:not([type="email"]):visible').first
        try:
            await code_inputs.wait_for(state="visible", timeout=10000)
            await code_inputs.fill(code)
            await page.wait_for_timeout(2000)
        except:
            # Try JS
            await page.evaluate(f"""() => {{
                const inputs = Array.from(document.querySelectorAll('input[type="text"], input:not([type="email"])'));
                const vis = inputs.find(i => i.offsetParent !== null);
                if (vis) {{ vis.value = {json.dumps(code)}; vis.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            }}""")
            await page.wait_for_timeout(2000)
        await page.screenshot(path=f"{OUT_DIR}/05_code_filled.png")
        print(f"[*] URL: {page.url}")

        # Wait for profile/Turnstile
        print("[8] Waiting for Turnstile...")
        await page.wait_for_timeout(3000)
        
        # Try to solve Turnstile with patchright
        token = None
        for i in range(60):
            await page.wait_for_timeout(1000)
            token = await page.evaluate("""() => {
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                if (input && input.value && input.value.length > 100) return input.value;
                if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                    const t = window.turnstile.getResponse();
                    if (t) return t;
                }
                return null;
            }""")
            if token:
                print(f"[+] Turnstile AUTO-SOLVED by patchright! len={len(token)}")
                break
            if i % 10 == 0 and i > 0:
                print(f"[*] Still waiting... {i}s")
                # Try manual render
                await page.evaluate("""() => {
                    if (window.turnstile && typeof window.turnstile.render === 'function') {
                        document.querySelectorAll('.cf-turnstile, [data-sitekey]').forEach(el => {
                            try { window.turnstile.render(el); } catch(e) {}
                        });
                    }
                }""")

        if not token:
            print("[-] Turnstile not solved")
            await page.screenshot(path=f"{OUT_DIR}/06_no_turnstile.png")
            await browser.close()
            return None

        # Fill profile
        print("[9] Filling profile...")
        try:
            name_loc = page.locator('input[name*="name" i]:visible').first
            if await name_loc.count() > 0:
                await name_loc.fill("Brian Ma")
                await page.wait_for_timeout(300)
        except: pass
        try:
            dob_loc = page.locator('input[type="date"]:visible').first
            if await dob_loc.count() > 0:
                await dob_loc.fill("1995-06-15")
                await page.wait_for_timeout(300)
        except: pass
        await page.screenshot(path=f"{OUT_DIR}/07_profile.png")

        # Submit
        print("[10] Submitting profile...")
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
            const btn = btns.find(b => {
                const t = (b.textContent||'').toLowerCase();
                return (t.includes('sign up') || t.includes('continue') || t.includes('agree') || t.includes('submit')) && b.offsetParent !== null && !b.disabled;
            });
            if (btn) { btn.click(); return true; }
            return false;
        }""")
        await page.wait_for_timeout(5000)
        print(f"[*] URL: {page.url}")
        await page.screenshot(path=f"{OUT_DIR}/08_after_submit.png")

        # Check for second Turnstile
        token2 = await page.evaluate("""() => {
            const input = document.querySelector('input[name="cf-turnstile-response"]');
            if (input && input.value && input.value.length > 100) return input.value;
            if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                const t = window.turnstile.getResponse();
                if (t) return t;
            }
            return null;
        }""")
        if token2:
            print(f"[+] Second Turnstile already solved! len={len(token2)}")

        # Wait for SSO cookie
        print("[11] Waiting for SSO cookie...")
        sso = None
        for i in range(60):
            await page.wait_for_timeout(1000)
            cookies = await context.cookies()
            for c in cookies:
                if "sso" in c["name"].lower():
                    sso = c["value"]
                    break
            if sso: break
            # Also check page content for sso
            sso_in_page = await page.evaluate("""() => {
                return (document.body?.textContent || '').includes('sso');
            }""")
        await page.screenshot(path=f"{OUT_DIR}/09_final.png")

        if sso:
            print(f"[+] SSO: {sso[:40]}...")
            created, synced = import_sso(sso)
            print(f"[+] Gateway: created={created} synced={synced}")
            with open("/root/grok-x-farm/accounts.txt", "a") as f:
                f.write(f"{email}:{sso}\n")
            print(f"[+] Saved: {email}")
            await browser.close()
            return f"{email}:{sso}"
        else:
            all_cookies = await context.cookies()
            names = [c["name"] for c in all_cookies]
            print(f"[-] No SSO. Cookies: {names}")
            html = await page.content()
            with open(f"{OUT_DIR}/debug.html", "w") as f:
                f.write(html)
            print(f"[*] Debug HTML saved")
            await browser.close()
            return None

if __name__ == "__main__":
    result = asyncio.run(register())
    if result:
        print(f"\n=== SUCCESS: {result} ===")
    else:
        print("\n=== FAILED ===")
        sys.exit(1)