#!/usr/bin/env python3
"""grok_reg_v3.py — Human-like patchright registration with realistic timing."""
import asyncio, json, os, random, string, time, urllib.request, urllib.parse, re, sys

DUCKMAIL_API = "https://api.duckmail.sbs"
XAI_SIGNUP = "https://accounts.x.ai/sign-up?redirect=grok-com"
GATEWAY = "http://127.0.0.1:8000"
ADMIN_PASS = "iRaFzoZ2c20Nur"
OUT = "/root/grok-x-farm/screenshots"
os.makedirs(OUT, exist_ok=True)

# ======================== Duckmail + Gateway ========================
def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())
def http_post(url, data, headers=None):
    h = {"Content-Type":"application/json"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())
def get_domains():
    d = http_get(f"{DUCKMAIL_API}/domains")
    if isinstance(d,list) and d and isinstance(d[0],str): return d
    if isinstance(d,dict) and "hydra:member" in d: d = d["hydra:member"]
    return [x.get("domain","") if isinstance(x,dict) else str(x) for x in d if x]
def create_email(addr):
    return http_post(f"{DUCKMAIL_API}/accounts", {"address":addr,"password":"P@ssw0rd123!","expiresIn":0})
def get_token(addr):
    resp = http_post(f"{DUCKMAIL_API}/token", {"address": addr, "password": "P@ssw0rd123!"})
    return resp.get("token", "") if isinstance(resp, dict) else ""
def get_messages(token):
    resp = http_get(f"{DUCKMAIL_API}/messages", {"Authorization":f"Bearer {token}"})
    # Response is wrapped in hydra:member
    msgs = resp.get("hydra:member", []) if isinstance(resp, dict) else resp
    return msgs if isinstance(msgs, list) else []
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

# ======================== Patchright with human-like behavior ========================
async def human_type(page, locator, text, delay_min=80, delay_max=200):
    """Type text with random delays between characters."""
    await locator.click()
    await page.wait_for_timeout(random.randint(300, 700))
    for char in text:
        await page.keyboard.type(char, delay=random.randint(delay_min, delay_max))
    await page.wait_for_timeout(random.randint(400, 800))

async def human_click(page, locator):
    """Click a button with mouse movement simulation."""
    box = await locator.bounding_box()
    if box:
        # Move mouse from random position to the button center
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)
        target_x = box["x"] + box["width"] / 2 + random.randint(-5, 5)
        target_y = box["y"] + box["height"] / 2 + random.randint(-3, 3)
        await page.mouse.move(start_x, start_y)
        await page.wait_for_timeout(random.randint(100, 300))
        steps = random.randint(15, 30)
        for i in range(1, steps + 1):
            t = i / steps
            ease = t * t * (3 - 2 * t)  # smoothstep
            cur_x = start_x + (target_x - start_x) * ease
            cur_y = start_y + (target_y - start_y) * ease
            await page.mouse.move(cur_x, cur_y)
            await page.wait_for_timeout(random.randint(10, 40))
    await page.wait_for_timeout(random.randint(200, 500))
    await locator.click()
    await page.wait_for_timeout(random.randint(500, 1000))

async def register():
    from patchright.async_api import async_playwright

    # Create email
    domains = get_domains()
    domain = random.choice(domains) if domains else "niceground.shop"
    username = "".join(random.choices(string.ascii_lowercase+string.digits, k=10))
    email = f"{username}@{domain}"
    print(f"[EMAIL] {email}")
    create_email(email)

    async with async_playwright() as p:
        # Launch browser WITHOUT headless — Xvfb gives us virtual display
        browser = await p.chromium.launch(
            headless=False,
            executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage","--window-size=1920,1080",
                  "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width":1920,"height":1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["clipboard-read"]
        )
        # Remove webdriver detection
        await context.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = {runtime:{}};
        }""")
        
        page = await context.new_page()

        # 1. Open signup with random delay
        print("[1] Opening signup...")
        await page.goto(XAI_SIGNUP, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(random.randint(3000, 5000))
        await page.screenshot(path=f"{OUT}/v3_01.png")

        # 2. Dismiss cookie banner if present
        for btn_text in ["Accept All Cookies", "Reject All"]:
            try:
                btn = page.locator(f"button:has-text('{btn_text}')").first
                if await btn.count()>0 and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(random.randint(1000, 2000))
            except: pass

        # 3. Human-like click on "Sign up with email"
        print("[2] Clicking 'Sign up with email'...")
        email_btn = page.locator("button:has-text('Sign up with email')").first
        await human_click(page, email_btn)
        await page.wait_for_timeout(random.randint(2000, 3000))
        await page.screenshot(path=f"{OUT}/v3_02.png")

        # 4. Email input
        print("[3] Filling email...")
        email_sel = 'input[data-testid="email"], input[name="email"], input[type="email"]'
        email_loc = page.locator(email_sel).first
        await email_loc.wait_for(state="visible", timeout=15000)
        await human_type(page, email_loc, email, delay_min=80, delay_max=180)
        actual = await email_loc.input_value()
        print(f"  Filled: {actual}")
        if actual != email:
            print(f"  MISMATCH! Retrying...")
            await email_loc.click()
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(300)
            await human_type(page, email_loc, email, delay_min=120, delay_max=250)
            actual = await email_loc.input_value()
            print(f"  After retry: {actual}")

        # 5. Human-like click on "Sign up"
        print("[4] Clicking 'Sign up'...")
        await page.wait_for_timeout(random.randint(1500, 2500))
        signup_btn = page.locator("button:has-text('Sign up'):not(:has-text('email')):not(:has-text('Go back')):not(:has-text('Apple')):not(:has-text('Google')):not(:has-text('GitHub')):not(:has-text('with X'))").first
        if await signup_btn.count()>0 and await signup_btn.is_enabled():
            await human_click(page, signup_btn)
        print(f"  URL: {page.url}")
        await page.wait_for_timeout(random.randint(3000, 5000))
        await page.screenshot(path=f"{OUT}/v3_03.png")

        # Detect page change by content (React SPA - URL doesn't change)
        page_text = await page.evaluate("() => document.body?.textContent || ''")
        if "Verify your email" in page_text or "verification" in page_text.lower():
            print("[+] Page advanced to verification step!")
        else:
            print(f"[-] Page didn't advance. Content preview: {page_text[:200]}")
            # Try clicking again
            signup_btn2 = page.locator("button:has-text('Sign up'):not(:has-text('email')):not(:has-text('Go back')):not(:has-text('with'))").first
            if await signup_btn2.count()>0:
                await signup_btn2.click()
                await page.wait_for_timeout(3000)

        # 6. Wait for verification code
        print("[5] Waiting for verification code...")
        code = wait_for_code(email, timeout=120)
        if not code:
            # Check for error on page
            err = await page.evaluate("""() => {
                const red = document.querySelector('[class*="error"], [class*="Error"], [style*="red"]');
                return red ? red.textContent : null;
            }""")
            print(f"  ERROR on page: {err}")
            await browser.close()
            return None
        print(f"  Code: {code}")

        # 7. Fill code
        print("[6] Filling code...")
        await page.wait_for_timeout(random.randint(1000, 2000))
        code_loc = page.locator('input[type="text"]:visible, input:not([type="email"]):not([type="password"]):visible').first
        try:
            await code_loc.wait_for(state="visible", timeout=10000)
            await human_type(page, code_loc, code, delay_min=50, delay_max=120)
        except:
            # Fallback: find any visible text input
            await page.evaluate(f"""() => {{
                const inputs = Array.from(document.querySelectorAll('input'));
                const vis = inputs.find(i => i.offsetParent!==null && i.type!=='email');
                if (vis) {{
                    vis.focus();
                    vis.value = {json.dumps(code)};
                    vis.dispatchEvent(new InputEvent('input',{{bubbles:true,data:{json.dumps(code)}}}));
                }}
            }}""")
        await page.wait_for_timeout(random.randint(2000, 3000))
        await page.screenshot(path=f"{OUT}/v3_04.png")
        print(f"  URL: {page.url}")

        # 8. Fill profile FIRST, then solve Turnstile
        print("[7] Filling profile fields...")
        await page.wait_for_timeout(random.randint(1000, 2000))
        
        # Find all visible text inputs
        all_inputs = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input'))
                .filter(i => i.offsetParent !== null)
                .map(i => ({type: i.type, name: i.name||'', id: i.id||'', placeholder: i.placeholder||'', 
                           autocomplete: i.autocomplete||'', value: i.value.substring(0,20)}))
                .slice(0, 10);
        }""")
        print(f"  Visible inputs: {json.dumps(all_inputs, indent=2)}")
        
        # Fill first name
        try:
            fn = page.locator('#givenName, input[name="givenName"]').first
            await fn.click()
            await page.wait_for_timeout(200)
            await fn.fill("Brian")
            await page.wait_for_timeout(300)
            print(f"  First name: {await fn.input_value()}")
        except Exception as e:
            print(f"  First name error: {e}")
        
        # Fill last name
        try:
            ln = page.locator('#familyName, input[name="familyName"]').first
            await ln.click()
            await page.wait_for_timeout(200)
            await ln.fill("Ma")
            await page.wait_for_timeout(300)
            print(f"  Last name: {await ln.input_value()}")
        except Exception as e:
            print(f"  Last name error: {e}")
        
        # Fill password
        try:
            pw = page.locator('#password, input[name="password"]').first
            await pw.click()
            await page.wait_for_timeout(200)
            await pw.fill("SecureP@ssw0rd99!")
            await page.wait_for_timeout(300)
            print(f"  Password filled")
        except Exception as e:
            print(f"  Password error: {e}")
        
        await page.screenshot(path=f"{OUT}/v3_05_profile.png")
        
        # 8b. Solve Turnstile — CLICK the checkbox first (patchright anti-detect should auto-solve)
        print("[8] Solving Turnstile...")
        token = None
        
        # Try clicking the Turnstile checkbox in the iframe
        print("  Clicking Turnstile checkbox...")
        try:
            # Find the Turnstile iframe and click the checkbox
            ts_frame = page.frame_locator('iframe[src*="turnstile"]').first
            # The checkbox is usually a label or input inside the iframe
            await ts_frame.locator('body').click()
            print("  Clicked Turnstile iframe body")
        except Exception as e:
            print(f"  Turnstile iframe click failed: {e}, trying direct mouse...")
            # Try clicking on the Turnstile widget area directly
            ts_div = page.locator('.cf-turnstile, [data-sitekey]').first
            if await ts_div.count() > 0:
                box = await ts_div.bounding_box()
                if box:
                    await page.mouse.click(box["x"] + 30, box["y"] + 30)
                    print(f"  Clicked at Turnstile position")
        
        await page.wait_for_timeout(3000)
        
        # Wait for auto-solve (patchright should handle this)
        for i in range(30):
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
                print(f"  [+] Turnstile AUTO-SOLVED by patchright! len={len(token)}")
                break
            if i % 5 == 0:
                print(f"  Waiting for auto-solve... {i}s")
                # Try clicking again
                try:
                    ts_frame = page.frame_locator('iframe[src*="turnstile"]').first
                    await ts_frame.locator('body').click()
                except: pass
        
        # If not auto-solved, use 2captcha + call callback
        if not token:
            print("  Auto-solve failed, trying 2captcha...")
            try:
                import urllib.parse as _up
                current_url = page.url
                api_key = "f22d87c5fc2c3970f967c2b23dd3469e"
                sitekey = "0x4AAAAAAAhr9JGVDZbrZOo0"
                data = _up.urlencode({"key":api_key,"method":"turnstile","sitekey":sitekey,"pageurl":current_url,"json":"1"}).encode()
                req = urllib.request.Request("https://2captcha.com/in.php", data=data)
                with urllib.request.urlopen(req, timeout=30) as r:
                    task_resp = json.loads(r.read())
                task_id = task_resp.get("request","")
                print(f"  2captcha task: {task_id}")
                
                for _ in range(30):
                    await page.wait_for_timeout(3000)
                    url2 = f"https://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
                    with urllib.request.urlopen(url2, timeout=15) as r:
                        r2 = json.loads(r.read())
                    if r2.get("status") == 1:
                        token = r2["request"]
                        print(f"  [+] 2captcha solved! len={len(token)}")
                        break
            except Exception as e:
                print(f"  [!] 2captcha failed: {e}")
        
        if not token:
            print("[-] Turnstile not solved")
            await page.screenshot(path=f"{OUT}/v3_timeout.png")
            await browser.close()
            return None
        
        # Inject token AND call Turnstile callback to mark widget as solved
        await page.evaluate(f"""() => {{
            var input = document.querySelector('input[name="cf-turnstile-response"]');
            if (!input) {{
                input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'cf-turnstile-response';
                document.body.appendChild(input);
            }}
            input.value = {json.dumps(token)};
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
            
            // Try to call turnstile callback to mark widget as solved
            if (window.turnstile) {{
                // Reset and re-execute with the token
                try {{
                    const widgets = document.querySelectorAll('[data-sitekey], .cf-turnstile');
                    widgets.forEach(w => {{
                        const id = w.getAttribute('data-turnstile-id') || w.id;
                        if (id) {{
                            try {{ window.turnstile.reset(id); }} catch(e) {{}}
                        }}
                    }});
                }} catch(e) {{}}
                
                // Force execute
                try {{ window.turnstile.execute(); }} catch(e) {{}}
                
                // Try to manually trigger callback
                try {{
                    const cb = window.turnstile._callbacks;
                    if (cb) Object.values(cb).forEach(fn => typeof fn === 'function' && fn({json.dumps(token)}));
                }} catch(e) {{}}
            }}
        }}""")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=f"{OUT}/v3_06_turnstile.png")
        
        # 9. Submit profile form
        print("[9] Submitting profile...")
        submit_btn = page.locator("button:has-text('Complete sign up'), button:has-text('Sign up'), button:has-text('Continue'), button:has-text('Agree')").first
        if await submit_btn.count()>0 and await submit_btn.is_enabled():
            await human_click(page, submit_btn)
        await page.wait_for_timeout(random.randint(5000, 8000))
        await page.screenshot(path=f"{OUT}/v3_06_final.png")
        print(f"  URL: {page.url}")

        # 11. Second Turnstile check
        token2 = await page.evaluate("""() => {
            const input = document.querySelector('input[name="cf-turnstile-response"]');
            if (input && input.value && input.value.length>100) return input.value;
            return null;
        }""")
        if token2:
            print(f"[*] Second Turnstile solved: len={len(token2)}")
            submit2 = page.locator("button:has-text('Continue'), button:has-text('Sign up'), button:has-text('Agree')").first
            if await submit2.count()>0:
                await submit2.click()
                await page.wait_for_timeout(5000)

        # 12. Get SSO
        print("[10] Getting SSO...")
        sso = None
        for i in range(120):
            await page.wait_for_timeout(1000)
            cookies = await context.cookies()
            for c in cookies:
                if "sso" in c["name"].lower():
                    sso = c["value"]
                    break
            if sso: break

        if sso:
            print(f"[+] SSO: {sso[:50]}...")
            created, synced = import_sso(sso)
            print(f"[+] Gateway: created={created} synced={synced}")
            with open("/root/grok-x-farm/accounts.txt","a") as f:
                f.write(f"{email}:{sso}\n")
            await browser.close()
            return f"{email}:{sso}"
        else:
            all_cookies = await context.cookies()
            print(f"[-] No SSO. Cookies: {[c['name'] for c in all_cookies]}")
            await browser.close()
            return None

if __name__=="__main__":
    r = asyncio.run(register())
    print(f"\n{'SUCCESS' if r else 'FAILED'}: {r}")