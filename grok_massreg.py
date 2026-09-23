#!/usr/bin/env python3
"""grok_massreg.py — Pure Python mass registration for Grok accounts.
No browser needed. Uses x.ai API directly + duckmail + 2captcha.

Usage:
  python grok_massreg.py --count 5
  python grok_massreg.py --count 10 --import-gateway

Flow per account (~15s):
  1. Create duckmail email
  2. POST /api/auth/send-verification-code
  3. Poll duckmail for code
  4. POST /api/auth/sign-up/verify-email
  5. Solve Turnstile via 2captcha
  6. POST /api/auth/sign-up/create-account → SSO cookie
  7. Import SSO into grok2api gateway
"""
import argparse, json, os, random, re, string, sys, time, urllib.request, urllib.parse, urllib.error

# ─── Config ───
DUCKMAIL = "https://api.duckmail.sbs"
XAI_BASE = "https://accounts.x.ai"
GATEWAY = os.getenv("G2A_BASE", "http://127.0.0.1:8000")
ADMIN_PASS = os.getenv("G2A_ADMIN_PASS", "iRaFzoZ2c20Nur")
TWOCAPTCHA_KEY = os.getenv("TWOCAPTCHA_KEY", "f22d87c5fc2c3970f967c2b23dd3469e")
TURNSTILE_SITEKEY = "0x4AAAAAAAhr9JGVDZbrZOo0"
SIGNUP_URL = "https://accounts.x.ai/sign-up?redirect=grok-com"
PASSWORD = "SecureP@ssw0rd99!"
ACCOUNTS_FILE = "/root/grok-x-farm/accounts.txt"
PROXY = None  # Set to "http://ip:port" if needed

# ─── HTTP with cookie jar ───
import http.cookiejar
def make_session():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"),
        ("Accept", "application/json"),
        ("Content-Type", "application/json"),
        ("Origin", "https://accounts.x.ai"),
        ("Referer", "https://accounts.x.ai/sign-up?redirect=grok-com"),
    ]
    return opener, cj

def api_post(session, url, data, retries=3):
    """POST with retry on 401 — re-do send-code if session expired."""
    last_err = None
    for attempt in range(retries):
        try:
            body = json.dumps(data).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with session.open(req, timeout=30) as r:
                resp_body = r.read().decode()
                return r.status, resp_body, r.headers
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 401 and attempt < retries - 1:
                time.sleep(2)
                continue
            return e.code, e.read().decode()[:500], {}
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise
    raise last_err

def api_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

# ─── Duckmail ───
def get_domains():
    d = api_get(f"{DUCKMAIL}/domains")
    if isinstance(d, list) and d and isinstance(d[0], str): return d
    if isinstance(d, dict) and "hydra:member" in d: d = d["hydra:member"]
    return [x.get("domain","") if isinstance(x, dict) else str(x) for x in d if x]

def create_email(addr):
    data = json.dumps({"address": addr, "password": PASSWORD, "expiresIn": 0}).encode()
    req = urllib.request.Request(f"{DUCKMAIL}/accounts", data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())

def get_token(addr):
    data = json.dumps({"address": addr, "password": PASSWORD}).encode()
    req = urllib.request.Request(f"{DUCKMAIL}/token", data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("token", "")

def get_messages(token):
    resp = api_get(f"{DUCKMAIL}/messages", {"Authorization": f"Bearer {token}"})
    msgs = resp.get("hydra:member", []) if isinstance(resp, dict) else resp
    return msgs if isinstance(msgs, list) else []

def wait_for_code(addr, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            tok = get_token(addr)
            for msg in get_messages(tok):
                recips = [t.get("address","").lower() for t in (msg.get("to") or [])]
                if addr.lower() not in recips: continue
                txt = str(msg.get("subject","")) + " " + str(msg.get("text","")) + " " + str(msg.get("html",""))
                m = re.search(r'\b(\d{3}[-\s]?\d{3})\b', txt)
                if m: return m.group(1).replace(" ", "-")
        except: pass
        time.sleep(3)
    return None

# ─── 2captcha ───
def solve_turnstile(page_url):
    data = urllib.parse.urlencode({
        "key": TWOCAPTCHA_KEY,
        "method": "turnstile",
        "sitekey": TURNSTILE_SITEKEY,
        "pageurl": page_url,
        "json": "1",
    }).encode()
    req = urllib.request.Request("https://2captcha.com/in.php", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    if resp.get("status") != 1:
        raise Exception(f"2captcha submit failed: {resp}")
    task_id = resp["request"]
    
    for _ in range(30):
        time.sleep(3)
        url = f"https://2captcha.com/res.php?key={TWOCAPTCHA_KEY}&action=get&id={task_id}&json=1"
        with urllib.request.urlopen(url, timeout=15) as r:
            r2 = json.loads(r.read())
        if r2.get("status") == 1:
            return r2["request"]
        if r2.get("request") != "CAPCHA_NOT_READY":
            raise Exception(f"2captcha error: {r2}")
    raise Exception("2captcha timeout")

# ─── Gateway import ───
def import_sso(sso):
    data = json.dumps({"username": "admin", "password": ADMIN_PASS}).encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/auth/login", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read())["data"]["tokens"]["accessToken"]
    
    boundary = "----" + "".join(random.choices(string.ascii_lowercase, k=12))
    mp = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sso.txt\"\r\n"
          f"Content-Type: text/plain\r\n\r\n{sso}\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/accounts/web/import", data=mp,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
    m = re.search(r'"created":(\d+).*?"synced":(\d+)', body)
    return m.groups() if m else ("?", "?")

def convert_to_build():
    """Convert all Web pool accounts to Build pool."""
    data = json.dumps({"username": "admin", "password": ADMIN_PASS}).encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/auth/login", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read())["data"]["tokens"]["accessToken"]
    
    data = json.dumps({"all": True, "strategy": "missing"}).encode()
    req = urllib.request.Request(f"{GATEWAY}/api/admin/v1/accounts/web/convert-to-build", data=data,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode()[-200:]

# ─── Register one account ───
def register_one():
    session, cookie_jar = make_session()
    
    # 1. Create email
    domains = get_domains()
    domain = random.choice(domains) if domains else "niceground.shop"
    username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@{domain}"
    print(f"  [1/7] Email: {email}")
    create_email(email)
    
    # 2. Send verification code
    print(f"  [2/7] Sending verification code...")
    status, body, _ = api_post(session, f"{XAI_BASE}/api/auth/send-verification-code", {
        "email": email,
        "castleRequestToken": "",
    })
    if status != 200:
        print(f"  [-] send-code failed: {status} {body[:100]}")
        return None
    
    # 3. Get code from duckmail
    print(f"  [3/7] Waiting for code...")
    code = wait_for_code(email, timeout=90)
    if not code:
        print(f"  [-] No code received")
        return None
    code_clean = code.replace("-", "")
    print(f"  [+] Code: {code}")
    
    # 4. Verify email
    print(f"  [4/7] Verifying email...")
    status, body, _ = api_post(session, f"{XAI_BASE}/api/auth/sign-up/verify-email", {
        "email": email,
        "code": code_clean,
    })
    if status != 200:
        print(f"  [-] verify-email failed: {status} {body[:100]}")
        return None
    
    # 5. Solve Turnstile
    print(f"  [5/7] Solving Turnstile (2captcha)...")
    token = solve_turnstile(SIGNUP_URL)
    print(f"  [+] Turnstile solved: len={len(token)}")
    
    # 6. Create account
    print(f"  [6/7] Creating account...")
    status, body, headers = api_post(session, f"{XAI_BASE}/api/auth/sign-up/create-account", {
        "email": email,
        "password": PASSWORD,
        "givenName": "Brian",
        "familyName": "Ma",
        "emailValidationCode": code_clean,
        "turnstileToken": token,
        "cf-turnstile-response": token,
        "marketingOptIn": False,
        "castleRequestToken": "",
    })
    
    if status != 200:
        print(f"  [-] create-account failed: {status} {body[:200]}")
        return None
    
    # Extract SSO from cookies
    sso = None
    for cookie in cookie_jar:
        if "sso" in cookie.name.lower():
            sso = cookie.value
            break
    
    if not sso:
        # Try to find in response body
        try:
            resp_data = json.loads(body)
            sso = resp_data.get("session", {}).get("token") or resp_data.get("ssoToken")
        except: pass
    
    if not sso:
        print(f"  [-] No SSO in cookies or response. Body: {body[:200]}")
        print(f"  Cookies: {[c.name for c in cookie_jar]}")
        return None
    
    print(f"  [+] SSO: {sso[:40]}...")
    
    # 7. Import to gateway
    print(f"  [7/7] Importing to gateway...")
    created, synced = import_sso(sso)
    print(f"  [+] Gateway: created={created} synced={synced}")
    
    # Save
    with open(ACCOUNTS_FILE, "a") as f:
        f.write(f"{email}:{sso}\n")
    
    return email

# ─── Main ───
def main():
    ap = argparse.ArgumentParser(description="Mass register Grok accounts")
    ap.add_argument("--count", type=int, default=5, help="Number of accounts to register")
    ap.add_argument("--import-gateway", action="store_true", default=True, help="Auto-import SSO to gateway")
    ap.add_argument("--convert-build", action="store_true", default=True, help="Convert Web→Build after import")
    args = ap.parse_args()
    
    print(f"=== Grok Mass Registration ===")
    print(f"Count: {args.count}")
    print(f"Gateway: {GATEWAY}")
    print(f"2captcha key: {TWOCAPTCHA_KEY[:10]}...")
    print()
    
    ok = 0
    fail = 0
    for i in range(args.count):
        print(f"\n--- Account {i+1}/{args.count} ---")
        try:
            result = register_one()
            if result:
                ok += 1
                print(f"  ✅ SUCCESS: {result}")
            else:
                fail += 1
                print(f"  ❌ FAILED")
        except Exception as e:
            fail += 1
            print(f"  ❌ ERROR: {e}")
        
        if i < args.count - 1:
            delay = random.randint(3, 8)
            print(f"  Waiting {delay}s before next account...")
            time.sleep(delay)
    
    print(f"\n=== RESULTS ===")
    print(f"Success: {ok}/{args.count}")
    print(f"Failed: {fail}/{args.count}")
    print(f"Accounts saved to: {ACCOUNTS_FILE}")
    
    if args.convert_build and ok > 0:
        print(f"\nConverting Web→Build pool...")
        try:
            result = convert_to_build()
            print(f"  Convert result: {result[-100:]}")
        except Exception as e:
            print(f"  Convert failed: {e}")
    
    print(f"\n=== DONE ===")

if __name__ == "__main__":
    main()
