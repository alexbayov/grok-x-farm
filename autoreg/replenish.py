#!/usr/bin/env python3
"""replenish.py — full cycle: autoreg Grok accounts → import SSO into grok2api → convert Web→Build.

Usage:
  python replenish.py --count 5              # reg 5 accounts and push to gateway
  python replenish.py --import-only          # only import already-registered (accounts.txt)
  python replenish.py --count 3 --threads 2

Env config (or edit defaults below):
  REG_DIR       path to grok-auto clone (with .venv and keys/accounts.txt)
  G2A_BASE      gateway base URL (default http://127.0.0.1:8000)
  SECRETS_FILE  file with a line "admin password: XXX" (gateway admin creds)
  MARKER_FILE   idempotency marker (default ./imported_sso.txt next to this script)
  G2A_ADMIN_USER / G2A_ADMIN_PASS  direct admin creds (overrides SECRETS_FILE)
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request, urllib.error, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REG_DIR = os.getenv("REG_DIR", r"C:\Users\User\grok-reg\grok-auto")
ACCOUNTS = os.path.join(REG_DIR, "keys", "accounts.txt")
GATEWAY = os.getenv("G2A_BASE", "http://127.0.0.1:8000")
SECRETS = os.getenv("SECRETS_FILE", "")
MARKER = os.getenv("MARKER_FILE", os.path.join(HERE, "imported_sso.txt"))


def admin_token():
    user = os.getenv("G2A_ADMIN_USER", "admin")
    pw = os.getenv("G2A_ADMIN_PASS")
    if not pw:
        pw = re.search(r"admin password: (\S+)", open(SECRETS, encoding="utf-8").read()).group(1)
    data = json.dumps({"username": user, "password": pw}).encode()
    req = urllib.request.Request(GATEWAY + "/api/admin/v1/auth/login", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["data"]["tokens"]["accessToken"]


def import_sso(tok, sso):
    boundary = uuid.uuid4().hex
    mp = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sso.txt\"\r\n"
          f"Content-Type: text/plain\r\n\r\n{sso}\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(GATEWAY + "/api/admin/v1/accounts/web/import", data=mp,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
    m = re.search(r'"created":(\d+).*?"synced":(\d+)', body)
    return m.groups() if m else ("?", "?")


def convert_to_build(tok):
    data = json.dumps({"all": True, "strategy": "missing"}).encode()
    req = urllib.request.Request(GATEWAY + "/api/admin/v1/accounts/web/convert-to-build", data=data,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode()[-200:]


def run_reg(count, threads):
    py = os.path.join(REG_DIR, ".venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        py = os.path.join(REG_DIR, ".venv", "bin", "python")
    cmd = [py, "grok_auto.py", "--count", str(count), "--email-provider", "tmail"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.Popen(cmd, cwd=REG_DIR, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    if p.stdin:
        p.stdin.write(f"{threads}\n"); p.stdin.flush()
    for line in p.stdout or []:
        print("[REG]", line.rstrip())
    p.wait()
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--import-only", action="store_true")
    a = ap.parse_args()

    before = set(open(ACCOUNTS, encoding="utf-8").read().splitlines()) if os.path.exists(ACCOUNTS) else set()

    if a.count and not a.import_only:
        rc = run_reg(a.count, a.threads)
        print(f"[+] reg exit: {rc}")

    after = set(open(ACCOUNTS, encoding="utf-8").read().splitlines())
    new = sorted(after - before) if not a.import_only else sorted(after)
    imported = set(open(MARKER, encoding="utf-8").read().splitlines()) if os.path.exists(MARKER) else set()

    todo = [l for l in new if l.split(":")[0] not in imported]
    if not todo:
        print("[*] no new accounts to import"); return

    tok = admin_token()
    ok = 0
    for line in todo:
        parts = line.split(":")
        email, sso = parts[0], parts[-1]
        try:
            created, synced = import_sso(tok, sso)
            print(f"[+] {email} -> created:{created} synced:{synced}")
            ok += 1
            with open(MARKER, "a", encoding="utf-8") as f:
                f.write(email + "\n")
        except Exception as e:
            print(f"[!] {email} import failed: {e}")
        time.sleep(1)

    if ok:
        print("[+] convert web->build:", convert_to_build(tok)[-120:])
    print(f"[DONE] imported {ok}/{len(todo)}")


if __name__ == "__main__":
    main()
