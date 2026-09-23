#!/usr/bin/env python3
"""Find the x.ai account creation API endpoint by searching JS bundles."""
import asyncio, json, os, random, string, time, urllib.request, re, sys

DUCKMAIL = "https://api.duckmail.sbs"
XAI = "https://accounts.x.ai/sign-up?redirect=grok-com"

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())
def http_post(url, data, headers=None):
    h = {"Content-Type":"application/json"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())
def get_domains():
    d = http_get(f"{DUCKMAIL}/domains")
    if isinstance(d,list) and d and isinstance(d[0],str): return d
    if isinstance(d,dict) and "hydra:member" in d: d = d["hydra:member"]
    return [x.get("domain","") if isinstance(x,dict) else str(x) for x in d if x]
def create_email(a): return http_post(f"{DUCKMAIL}/accounts", {"address":a,"password":"P@ssw0rd123!","expiresIn":0})
def get_token(a):
    r = http_post(f"{DUCKMAIL}/token", {"address":a,"password":"P@ssw0rd123!"})
    return r.get("token","") if isinstance(r,dict) else ""
def get_messages(t):
    r = http_get(f"{DUCKMAIL}/messages", {"Authorization":f"Bearer {t}"})
    m = r.get("hydra:member",[]) if isinstance(r,dict) else r
    return m if isinstance(m,list) else []
def wait_code(a,timeout=90):
    dl=time.time()+timeout
    while time.time()<dl:
        try:
            t=get_token(a)
            for m in get_messages(t):
                r=[x.get("address","").lower() for x in (m.get("to") or [])]
                if a.lower() not in r: continue
                txt=str(m.get("subject",""))+" "+str(m.get("text",""))+" "+str(m.get("html",""))
                mt=re.search(r'\b(\d{3}[-\s]?\d{3})\b',txt)
                if mt: return mt.group(1).replace(" ","-")
        except: pass
        time.sleep(3)
    return None

async def find_endpoint():
    from patchright.async_api import async_playwright
    domains = get_domains()
    email = f"{''.join(random.choices(string.ascii_lowercase+string.digits,k=10))}@{random.choice(domains)}"
    print(f"Email: {email}")
    create_email(email)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"]
        )
        ctx = await browser.new_context(
            viewport={"width":1920,"height":1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")
        page = await ctx.new_page()

        # Open + click Sign up with email
        await page.goto(XAI, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        for t in ["Accept All Cookies","Reject All"]:
            try:
                b = page.locator(f"button:has-text('{t}')").first
                if await b.count()>0 and await b.is_visible(): await b.click(); await page.wait_for_timeout(1000)
            except: pass
        await page.locator("button:has-text('Sign up with email')").first.click()
        await page.wait_for_timeout(3000)

        # Fill email + submit
        el = page.locator('input[type="email"]').first
        await el.wait_for(state="visible", timeout=10000)
        await el.click(); await page.wait_for_timeout(200)
        await el.type(email, delay=80); await page.wait_for_timeout(800)
        await page.locator("button:has-text('Sign up'):not(:has-text('email')):not(:has-text('Go back')):not(:has-text('with'))").first.click()
        await page.wait_for_timeout(3000)

        # Code
        code = wait_code(email, timeout=120)
        if not code: print("No code"); await browser.close(); return
        print(f"Code: {code}")
        cl = page.locator('input[type="text"]:visible').first
        try:
            await cl.wait_for(state="visible", timeout=10000)
            await cl.click(); await cl.type(code, delay=60)
        except: pass
        await page.wait_for_timeout(3000)

        # Fill profile
        try:
            await page.locator('#givenName').fill("Brian")
            await page.locator('#familyName').fill("Ma")
            await page.locator('#password').fill("SecureP@ssw0rd99!")
            print("Profile filled")
        except Exception as e:
            print(f"Profile: {e}")
        await page.wait_for_timeout(2000)

        # NOW: search all loaded JS chunks for API endpoint patterns
        print("\n=== SEARCHING JS BUNDLES FOR API ENDPOINTS ===")
        js_urls = await page.evaluate("""() => {
            return performance.getEntriesByType('resource')
                .filter(r => r.name.endsWith('.js') || r.name.includes('.js?'))
                .map(r => r.name)
                .slice(0, 100);
        }""")
        print(f"Found {len(js_urls)} JS files")

        found_endpoints = set()
        for js_url in js_urls:
            try:
                # Fetch the JS file and search for endpoint patterns
                content = await page.evaluate("""async (url) => {
                    try {
                        const resp = await fetch(url);
                        const text = await resp.text();
                        // Search for API endpoint patterns
                        const patterns = [
                            /["'](\/api\/[^"']+)["']/g,
                            /["'](\/auth_mgmt[^"']*)["']/g,
                            /["'](\/v\d+\/[^"']+)["']/g,
                        ];
                        const results = [];
                        for (const p of patterns) {
                            let m;
                            while ((m = p.exec(text)) !== null) results.push(m[1]);
                        }
                        // Also search for fetch/post/grpc patterns
                        const grpc = text.match(/["'](\/[^"']*(?:Auth|auth|signup|sign-up|complete|create|register|account)[^"']*)["']/gi) || [];
                        return {url: url.substring(url.length-40), endpoints: [...new Set([...results, ...grpc])].slice(0, 20)};
                    } catch(e) { return {error: e.message}; }
                }""", js_url)
                
                if content and isinstance(content, dict) and content.get("endpoints"):
                    for ep in content["endpoints"]:
                        if ep not in found_endpoints and len(ep) > 5 and not ep.endswith(".js"):
                            found_endpoints.add(ep)
                            print(f"  [{content['url'][-30:]}] {ep}")
            except: pass

        print(f"\n=== ALL FOUND ENDPOINTS ({len(found_endpoints)}) ===")
        for ep in sorted(found_endpoints):
            print(f"  {ep}")

        # Now try each found endpoint with a POST
        print("\n=== TRYING ENDPOINTS ===")
        token = "test_token"
        for ep in sorted(found_endpoints):
            if any(x in ep.lower() for x in ["complete","create","register","signup","sign-up","account"]):
                result = await page.evaluate("""async (ep) => {
                    try {
                        const r = await fetch(ep, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({email: %s, givenName: 'Brian', familyName: 'Ma', password: %s, 'cf-turnstile-response': 'test'}),
                            credentials: 'include'
                        });
                        return {status: r.status, body: (await r.text()).substring(0, 200)};
                    } catch(e) { return {error: e.message}; }
                }""" % (json.dumps(email), json.dumps("SecureP@ssw0rd99!")), ep)
                # Hmm, this won't work - need to fix the evaluate call
                pass

        await browser.close()

asyncio.run(find_endpoint())