#!/usr/bin/env python3
"""grok_reg_patchright.py — Register Grok accounts using patchright (free Turnstile).
Uses duckmail API for temp email, patchright for browser automation.
"""
import asyncio, json, os, random, string, time, urllib.request, urllib.parse, re, sys

# ─── Config ───
DUCKMAIL_API = "https://api.duckmail.sbs"
XAI_SIGNUP = "https://accounts.x.ai/sign-up?redirect=grok-com"
GATEWAY = os.getenv("G2A_BASE", "http://127.0.0.1:8000")
ADMIN_USER = "admin"
ADMIN_PASS = os.getenv("G2A_ADMIN_PASS", "iRaFzoZ2c20Nur")

# ─── Duckmail API ───
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

def get_duckmail_domains():
    d = http_get(f"{DUCKMAIL_API}/domains")
    # API can return list of strings or list of dicts
    if isinstance(d, list) and d and isinstance(d[0], str):
        return d
    if isinstance(d, dict) and "hydra:member" in d:
        d = d["hydra:member"]
    return [x.get("domain","") if isinstance(x, dict) else str(x) for x in d if x]

def create_duckmail_account(email_addr, password="P@ssw0rd123!"):
    return http_post(f"{DUCKMAIL_API}/accounts", {"address": email_addr, "password": password, "expiresIn": 0})

def get_duckmail_token(email_addr, password="P@ssw0rd123!"):
    """Get auth token for reading messages."""
    data = urllib.parse.urlencode({"address": email_addr, "password": password}).encode()
    req = urllib.request.Request(f"{DUCKMAIL_API}/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("token","")
    except Exception:
        return ""

def get_duckmail_messages(token):
    return http_get(f"{DUCKMAIL_API}/messages", {"Authorization": f"Bearer {token}"})

def extract_code(text):
    """Extract verification code like 123-456 from text."""
    m = re.search(r'\b(\d{3}[-\s]?\d{3})\b', text)
    if m:
        return m.group(1).replace(" ", "-")
    return None

def wait_for_code(email_addr, password, timeout=120):
    token = get_duckmail_token(email_addr, password)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msgs = get_duckmail_messages(token)
            for msg in msgs:
                recipients = [t.get("address","").lower() for t in (msg.get("to") or [])]
                if email_addr.lower() not in recipients:
                    continue
                subject = str(msg.get("subject","") or "")
                body = str(msg.get("text","") or "") + str(msg.get("html","") or "")
                code = extract_code(subject + " " + body)
                if code:
                    return code
        except Exception:
            pass
        time.sleep(3)
    return None

# ─── Gateway import ───
def import_sso_to_gateway(sso_token):
    """Import SSO token into grok2api gateway."""
    # Login as admin
    data = json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/auth/login", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read())["data"]["tokens"]["accessToken"]
    
    # Import SSO (multipart)
    boundary = "----formdata" + "".join(random.choices(string.ascii_lowercase, k=12))
    mp = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sso.txt\"\r\n"
          f"Content-Type: text/plain\r\n\r\n{sso_token}\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/accounts/web/import", data=mp,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
    m = re.search(r'"created":(\d+).*?"synced":(\d+)', body)
    return m.groups() if m else ("?","?")

# ─── Registration with patchright ───
async def register_account():
    from patchright.async_api import async_playwright

    # 1. Create temp email
    domains = get_duckmail_domains()
    domain = random.choice(domains) if domains else "niceground.shop"
    username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@{domain}"
    password = "P@ssw0rd123!"
    print(f"[*] Creating temp email: {email}")
    try:
        create_duckmail_account(email, password)
        print(f"[+] Email created")
    except Exception as e:
        print(f"[!] Email creation failed: {e}")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--window-size=1920,1080"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 2. Open signup page
        print("[*] Opening x.ai signup...")
        await page.goto(XAI_SIGNUP, wait_until="domcontentloaded", timeout=60000)

        # 3. Click "Sign up with email"
        print("[*] Clicking 'Sign up with email'...")
        btn = page.locator("text=Sign up with email")
        await btn.first.click()
        await page.wait_for_timeout(2000)

        # 4. Fill email using patchright native fill (handles React properly)
        print(f"[*] Filling email: {email}")
        email_sel = 'input[data-testid="email"], input[name="email"], input[type="email"], input[autocomplete="email"]'
        email_loc = page.locator(email_sel).first
        await email_loc.wait_for(state="visible", timeout=10000)
        # Click first, then fill (focus + type)
        await email_loc.click()
        await page.wait_for_timeout(200)
        await email_loc.fill(email)
        await page.wait_for_timeout(500)
        # Verify value was set
        actual = await email_loc.input_value()
        print(f"[*] Email input value: {actual}")
        
        # Also dispatch React-compatible events as fallback
        if actual != email:
            print("[*] Native fill failed, trying JS...")
            await page.evaluate(f"""() => {{
                const input = document.querySelector('{email_sel}');
                if (!input) return;
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(input, {json.dumps(email)});
                input.dispatchEvent(new InputEvent('beforeinput', {{ bubbles: true, data: {json.dumps(email)}, inputType: 'insertText' }}));
                input.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: {json.dumps(email)}, inputType: 'insertText' }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}""")
            await page.wait_for_timeout(500)

        # Click submit — try keyboard Enter first, then button click
        print("[*] Submitting form...")
        await email_loc.press("Enter")
        await page.wait_for_timeout(2000)
        url_after_enter = page.url
        print(f"[*] After Enter, URL: {url_after_enter}")
        
        if url_after_enter == XAI_SIGNUP:
            # Try clicking the Sign up button
            clicked = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                const btn = btns.find(b => {
                    const t = (b.textContent || '').toLowerCase().trim();
                    return t === 'sign up' || (t.includes('sign up') && !t.includes('with email'));
                });
                if (btn && !btn.disabled) { btn.focus(); btn.click(); return btn.textContent.trim(); }
                return null;
            }""")
            print(f"[*] Clicked button: {clicked}")
            await page.wait_for_timeout(3000)
        print(f"[*] After email submit, URL: {page.url}")

        # 5. Wait for verification code
        print("[*] Waiting for verification code...")
        code = wait_for_code(email, password, timeout=120)
        if not code:
            print("[-] No verification code received")
            await browser.close()
            return None
        print(f"[+] Got code: {code}")

        # 6. Fill code
        # Code is like "123-456" — may need to fill in separate fields or one field
        code_input = page.locator('input[type="text"], input[name*="code" i], input[placeholder*="code" i]')
        count = await code_input.count()
        print(f"[*] Code input fields found: {count}")
        if count > 0:
            await code_input.first.fill(code)
            await page.wait_for_timeout(2000)
        print(f"[*] After code, URL: {page.url}")

        # 7. Profile page — fill name and birthdate
        await page.wait_for_timeout(2000)
        print("[*] Looking for profile fields...")

        # Fill name
        name_inputs = page.locator('input[name*="name" i], input[placeholder*="name" i]')
        name_count = await name_inputs.count()
        print(f"[*] Name inputs: {name_count}")
        if name_count > 0:
            await name_inputs.first.fill("Brian Ma")
        
        # Fill birthdate
        dob_inputs = page.locator('input[name*="birth" i], input[type="date"], input[placeholder*="birth" i]')
        dob_count = await dob_inputs.count()
        print(f"[*] DOB inputs: {dob_count}")
        if dob_count > 0:
            await dob_inputs.first.fill("1995-06-15")

        # 8. Wait for Turnstile
        print("[*] Waiting for Turnstile to auto-solve...")
        turnstile_solved = False
        for i in range(60):
            await page.wait_for_timeout(1000)
            token_len = await page.evaluate("""() => {
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                if (input && input.value && input.value.length > 20) return input.value.length;
                if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                    const t = window.turnstile.getResponse();
                    if (t && t.length > 20) return t.length;
                }
                return 0;
            }""")
            if token_len > 0:
                print(f"[+] Turnstile AUTO-SOLVED by patchright! token length={token_len}")
                turnstile_solved = True
                break
            if i % 10 == 0 and i > 0:
                print(f"[*] Still waiting for Turnstile... {i}s")
        
        if not turnstile_solved:
            print("[-] Turnstile did not auto-solve. Trying manual render...")
            await page.evaluate("""() => {
                if (window.turnstile && typeof window.turnstile.render === 'function') {
                    const container = document.querySelector('.cf-turnstile, [data-sitekey]') || document.body;
                    window.turnstile.render(container);
                }
            }""")
            await page.wait_for_timeout(10000)
            token_len = await page.evaluate("""() => {
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                return (input && input.value) ? input.value.length : 0;
            }""")
            if token_len > 0:
                print(f"[+] Turnstile solved after manual render! token length={token_len}")
                turnstile_solved = True

        # 9. Submit form
        if turnstile_solved:
            print("[*] Submitting profile form...")
            submit = page.locator("button[type='submit'], button:has-text('Continue'), button:has-text('Sign up'), button:has-text('Agree')")
            if await submit.count() > 0:
                await submit.first.click()
            await page.wait_for_timeout(5000)
            print(f"[*] After submit, URL: {page.url}")

        # 10. Wait for SSO cookie
        print("[*] Waiting for SSO cookie...")
        sso_cookie = None
        for i in range(60):
            await page.wait_for_timeout(1000)
            cookies = await context.cookies()
            for c in cookies:
                if "sso" in c["name"].lower() or "session" in c["name"].lower() and c["domain"].endswith("x.ai"):
                    sso_cookie = c
                    break
            if sso_cookie:
                break
            if i % 10 == 0 and i > 0:
                print(f"[*] Still waiting for SSO... {i}s")
                # Check for another Turnstile
                token_len = await page.evaluate("""() => {
                    const input = document.querySelector('input[name="cf-turnstile-response"]');
                    return (input && input.value && input.value.length > 20) ? input.value.length : 0;
                }""")
                if token_len > 0:
                    print(f"[*] Found another Turnstile already solved: {token_len}")
                    # Try submitting again
                    submit = page.locator("button[type='submit'], button:has-text('Continue'), button:has-text('Agree')")
                    if await submit.count() > 0:
                        await submit.first.click()

        if sso_cookie:
            print(f"[+] SSO cookie found: {sso_cookie['name']}={sso_cookie['value'][:30]}...")
            result = f"{email}:{sso_cookie['value']}"
            # Import to gateway
            try:
                created, synced = import_sso_to_gateway(sso_cookie['value'])
                print(f"[+] Gateway import: created={created} synced={synced}")
            except Exception as e:
                print(f"[!] Gateway import failed: {e}")
            # Save to file
            with open("/root/grok-x-farm/accounts.txt", "a") as f:
                f.write(result + "\n")
            print(f"[+] Account saved: {email}")
            await browser.close()
            return result
        else:
            all_cookies = await context.cookies()
            cookie_names = [c["name"] for c in all_cookies]
            print(f"[-] No SSO cookie found. All cookies: {cookie_names}")
            # Save page content for debugging
            content = await page.content()
            with open("/tmp/xai_debug.html", "w") as f:
                f.write(content)
            print("[*] Page content saved to /tmp/xai_debug.html")
            await browser.close()
            return None

if __name__ == "__main__":
    result = asyncio.run(register_account())
    if result:
        print(f"\n=== SUCCESS ===\n{result}")
    else:
        print("\n=== FAILED ===")
        sys.exit(1)
