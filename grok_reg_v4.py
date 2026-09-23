#!/usr/bin/env python3
"""grok_reg_v4.py — API interception approach.
Fills form, injects 2captcha token, monitors ALL network traffic
when 'Complete sign up' is clicked. If no API call goes out,
frontend is blocking — we bypass it with direct fetch()."""
import asyncio, json, os, random, string, time, urllib.request, urllib.parse, re, sys

DUCKMAIL_API = "https://api.duckmail.sbs"
XAI_SIGNUP = "https://accounts.x.ai/sign-up?redirect=grok-com"
GATEWAY = "http://127.0.0.1:8000"
ADMIN_PASS = "iRaFzoZ2c20Nur"
OUT = "/root/grok-x-farm/screenshots"
os.makedirs(OUT, exist_ok=True)

# ======================== Utils ========================
def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())
def http_post(url, data, headers=None):
    h = {"Content-Type":"application/json"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())
def get_domains():
    d = http_get(f"{DUCKMAIL_API}/domains")
    if isinstance(d,list) and d and isinstance(d[0],str): return d
    if isinstance(d,dict) and "hydra:member" in d: d = d["hydra:member"]
    return [x.get("domain","") if isinstance(x,dict) else str(x) for x in d if x]
def create_email(addr): return http_post(f"{DUCKMAIL_API}/accounts", {"address":addr,"password":"P@ssw0rd123!","expiresIn":0})
def get_token(addr):
    resp = http_post(f"{DUCKMAIL_API}/token", {"address":addr,"password":"P@ssw0rd123!"})
    return resp.get("token","") if isinstance(resp,dict) else ""
def get_messages(token):
    resp = http_get(f"{DUCKMAIL_API}/messages", {"Authorization":f"Bearer {token}"})
    msgs = resp.get("hydra:member",[]) if isinstance(resp,dict) else resp
    return msgs if isinstance(msgs,list) else []
def wait_for_code(addr, timeout=90):
    deadline = time.time()+timeout
    while time.time()<deadline:
        try:
            tok = get_token(addr)
            for msg in get_messages(tok):
                recips = [t.get("address","").lower() for t in (msg.get("to") or [])]
                if addr.lower() not in recips: continue
                txt = str(msg.get("subject",""))+" "+str(msg.get("text",""))+" "+str(msg.get("html",""))
                m = re.search(r'\b(\d{3}[-\s]?\d{3})\b', txt)
                if m: return m.group(1).replace(" ","-")
        except: pass
        time.sleep(3)
    return None
def solve_2captcha(page_url):
    api_key = "f22d87c5fc2c3970f967c2b23dd3469e"
    sitekey = "0x4AAAAAAAhr9JGVDZbrZOo0"
    data = urllib.parse.urlencode({"key":api_key,"method":"turnstile","sitekey":sitekey,"pageurl":page_url,"json":"1"}).encode()
    req = urllib.request.Request("https://2captcha.com/in.php", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    task_id = resp.get("request","")
    print(f"  2captcha task: {task_id}")
    for _ in range(30):
        time.sleep(3)
        url2 = f"https://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
        with urllib.request.urlopen(url2, timeout=15) as r:
            r2 = json.loads(r.read())
        if r2.get("status") == 1:
            print(f"  [+] 2captcha solved! len={len(r2['request'])}")
            return r2["request"]
    return None
def import_sso(sso):
    data = json.dumps({"username":"admin","password":ADMIN_PASS}).encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/auth/login", data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read())["data"]["tokens"]["accessToken"]
    b = "----"+"".join(random.choices(string.ascii_lowercase,k=12))
    mp = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sso.txt\"\r\nContent-Type: text/plain\r\n\r\n{sso}\r\n--{b}--\r\n").encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/accounts/web/import", data=mp,
                                 headers={"Authorization":f"Bearer {tok}","Content-Type":f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
    m = re.search(r'"created":(\d+).*?"synced":(\d+)', body)
    return m.groups() if m else ("?","?")

# ======================== Registration ========================
async def register():
    from patchright.async_api import async_playwright

    # Create email
    domains = get_domains()
    domain = random.choice(domains) if domains else "niceground.shop"
    username = "".join(random.choices(string.ascii_lowercase+string.digits, k=10))
    email = f"{username}@{domain}"
    pw = "SecureP@ssw0rd99!"
    print(f"[EMAIL] {email}")
    create_email(email)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage","--window-size=1920,1080",
                  "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width":1920,"height":1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            locale="en-US", timezone_id="America/New_York"
        )
        await context.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            window.chrome = {runtime:{}};
        }""")
        page = await context.new_page()

        # NETWORK MONITORING — log all API calls
        api_calls = []
        async def on_request(request):
            url = request.url
            if "x.ai" in url or "accounts" in url or "auth" in url or "signup" in url or "register" in url:
                entry = {"url":url, "method":request.method, "headers":dict(request.headers), "post_data":request.post_data}
                api_calls.append(entry)
                print(f"  [NET] {request.method} {url[:100]}")
                if request.post_data:
                    print(f"       POST data: {request.post_data[:300]}")
        page.on("request", lambda req: asyncio.create_task(on_request(req)))
        
        async def on_response(response):
            url = response.url
            if ("x.ai" in url or "accounts" in url) and response.status != 200:
                print(f"  [NET-RESP] {response.status} {url[:80]}")
                try:
                    body = await response.text()
                    if body: print(f"       Body: {body[:200]}")
                except: pass
        page.on("response", lambda resp: asyncio.create_task(on_response(resp)))

        # 1. Open signup
        print("[1] Opening signup...")
        await page.goto(XAI_SIGNUP, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # 2. Dismiss cookies + click "Sign up with email"
        for txt in ["Accept All Cookies", "Reject All"]:
            try:
                btn = page.locator(f"button:has-text('{txt}')").first
                if await btn.count()>0 and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(1000)
            except: pass

        print("[2] Clicking 'Sign up with email'...")
        await page.locator("button:has-text('Sign up with email')").first.click()
        await page.wait_for_timeout(3000)

        # 3. Fill email + submit
        print("[3] Filling email...")
        email_loc = page.locator('input[type="email"], input[name="email"]').first
        await email_loc.wait_for(state="visible", timeout=10000)
        await email_loc.click()
        await page.wait_for_timeout(200)
        await email_loc.type(email, delay=80)
        await page.wait_for_timeout(800)
        print(f"  Email: {await email_loc.input_value()}")

        # Click "Sign up" button
        signup_btn = page.locator("button:has-text('Sign up'):not(:has-text('email')):not(:has-text('Go back')):not(:has-text('with'))").first
        await signup_btn.click()
        await page.wait_for_timeout(3000)

        # 4. Wait for code
        print("[4] Waiting for code...")
        code = wait_for_code(email, timeout=120)
        if not code:
            print("[-] No code")
            await browser.close()
            return None
        print(f"  Code: {code}")

        # 5. Fill code
        print("[5] Filling code...")
        await page.wait_for_timeout(1000)
        code_loc = page.locator('input[type="text"]:visible, input:not([type="email"]):not([type="password"]):visible').first
        try:
            await code_loc.wait_for(state="visible", timeout=10000)
            await code_loc.click()
            await code_loc.type(code, delay=60)
        except:
            code_js = json.dumps(code)
            await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input'));
                const vis = inputs.find(i => i.offsetParent!==null && i.type!=='email');
                if (vis) { vis.focus(); vis.value = %s;
                vis.dispatchEvent(new InputEvent('input',{bubbles:true,data:%s})); }
            }""" % (code_js, code_js))
        await page.wait_for_timeout(3000)

        # 6. Fill profile
        print("[6] Filling profile...")
        await page.wait_for_timeout(1000)
        try:
            await page.locator('#givenName').fill("Brian")
            await page.locator('#familyName').fill("Ma")
            await page.locator('#password').fill(pw)
            print("  Profile filled")
        except Exception as e:
            print(f"  Profile error: {e}")

        # 7. Solve Turnstile via 2captcha
        print("[7] Solving Turnstile via 2captcha...")
        token = solve_2captcha(page.url)
        if not token:
            print("[-] Turnstile not solved")
            await browser.close()
            return None

        # 8. Inject token + MONKEY-PATCH turnstile so frontend thinks it's solved
        print("[8] Patching Turnstile frontend...")
        token_js = json.dumps(token)
        await page.evaluate("""() => {
            // 1. Set the hidden input
            var input = document.querySelector('input[name="cf-turnstile-response"]');
            if (!input) {
                input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'cf-turnstile-response';
                document.body.appendChild(input);
            }
            input.value = %s;
            
            // 2. Monkey-patch window.turnstile so getResponse() returns our token
            if (window.turnstile) {
                window.turnstile.getResponse = function() { return %s; };
                window.turnstile.execute = function() {};
                window.turnstile.reset = function() {};
                // Try to patch internal widget state
                try {
                    var widgets = document.querySelectorAll('[data-sitekey], .cf-turnstile');
                    widgets.forEach(function(w) {
                        w.setAttribute('data-response', %s);
                    });
                } catch(e) {}
            }
            
            // 3. Dispatch events to trigger React state update
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            
            // 4. Also patch any global validation flags
            window.__turnstile_solved = true;
        }""" % (token_js, token_js, token_js))
        await page.wait_for_timeout(2000)
        await page.screenshot(path=f"{OUT}/v4_patched.png")
        
        # Verify the patch worked
        check = await page.evaluate("""() => {
            return {
                inputValue: (document.querySelector('input[name="cf-turnstile-response"]') || {}).value?.substring(0, 20),
                getResponse: window.turnstile ? (typeof window.turnstile.getResponse === 'function' ? window.turnstile.getResponse()?.substring(0,20) : 'not-func') : 'no-turnstile'
            };
        }""")
        print(f"  Patch check: {json.dumps(check)}")

        # 9. Click "Complete sign up" and MONITOR network
        print("[8] Clicking 'Complete sign up' (monitoring network)...")
        api_calls.clear()
        
        complete_btn = page.locator("button:has-text('Complete sign up')").first
        if await complete_btn.count()>0:
            await complete_btn.click()
        
        await page.wait_for_timeout(5000)
        await page.screenshot(path=f"{OUT}/v4_after_submit.png")
        
        # Check SSO after button click
        cookies = await context.cookies()
        sso = None
        for c in cookies:
            if "sso" in c["name"].lower():
                sso = c["value"]
                break
        
        if not sso:
            # Try DIRECT API CALLS — bypass frontend Turnstile validation entirely
            print("\n[9] Frontend blocked. Trying direct API calls...")
            
            # Try the REAL endpoint found in JS: sign-up/create-account
            # First, get the Castle request token from the page
            castle_token = await page.evaluate("""() => {
                // Try Castle SDK
                if (window.castle && typeof window.castle.generateRequestToken === 'function') {
                    return window.castle.generateRequestToken();
                }
                if (window.castle && typeof window.castle.createRequestToken === 'function') {
                    return window.castle.createRequestToken();
                }
                // Try to find castle token in page state
                if (window.__castle) return window.__castle;
                return null;
            }""")
            print(f"  Castle token: {str(castle_token)[:60] if castle_token else 'null'}")
            
            # If no castle SDK, try to extract from the last send-verification-code request
            if not castle_token:
                castle_token = await page.evaluate("""() => {
                    // Castle token might be in a hidden field or React state
                    const hidden = document.querySelector('input[name*="castle" i]');
                    if (hidden && hidden.value) return hidden.value;
                    // Check data attributes
                    const el = document.querySelector('[data-castle-token]');
                    if (el) return el.getAttribute('data-castle-token');
                    return null;
                }""")
                print(f"  Castle (alt): {str(castle_token)[:60] if castle_token else 'null'}")
            
            # Call the REAL endpoint
            ep = "/api/auth/sign-up/create-account"
            result = await page.evaluate("""async () => {
                try {
                    const body = {
                        email: %s,
                        password: %s,
                        givenName: 'Brian',
                        familyName: 'Ma',
                        emailValidationCode: %s,
                        turnstileToken: %s,
                        'cf-turnstile-response': %s,
                        marketingOptIn: false,
                        castleRequestToken: %s
                    };
                    const resp = await fetch(%s, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(body),
                        credentials: 'include'
                    });
                    const text = await resp.text();
                    return {status: resp.status, body: text.substring(0, 500)};
                } catch(e) { return {error: e.message}; }
            }""" % (json.dumps(email), json.dumps(pw), json.dumps(code), json.dumps(token), json.dumps(token), json.dumps(castle_token or ""), json.dumps(ep)))
            print(f"  {ep}: status={result.get('status')} body={result.get('body','')[:200]}")
            
            # Check for SSO
            cookies = await context.cookies()
            for c in cookies:
                if "sso" in c["name"].lower():
                    sso = c["value"]
                    print(f"  [+] SSO found!")
                    break
        
        # Final SSO check
        cookies = await context.cookies()
        sso = None
        for c in cookies:
            if "sso" in c["name"].lower():
                sso = c["value"]
                break
        
        if sso:
            print(f"\n[+] SSO FOUND: {sso[:50]}...")
            created, synced = import_sso(sso)
            print(f"[+] Gateway: created={created} synced={synced}")
            with open("/root/grok-x-farm/accounts.txt","a") as f:
                f.write(f"{email}:{sso}\n")
        else:
            print(f"\n[-] No SSO. Cookies: {[c['name'] for c in cookies]}")
            print(f"\n=== API CALLS: {len(api_calls)} ===")
            for call in api_calls:
                if 'mp/track' not in call['url'] and 'monitoring' not in call['url'] and 'observability' not in call['url']:
                    print(f"  {call['method']} {call['url'][:120]}")
                    if call.get('post_data'):
                        print(f"    POST: {call['post_data'][:200]}")
        
        await browser.close()
        return sso

if __name__=="__main__":
    r = asyncio.run(register())
    print(f"\n{'SUCCESS' if r else 'FAILED'}: {str(r)[:80] if r else 'None'}")