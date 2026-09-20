---
name: grok-x-parser-farm
description: Use when parsing/scraping X (Twitter) posts for free, farming Grok accounts, or operating the grok2api gateway pool.
version: 1
author: ENI/Gothbreach
license: MIT
metadata:
  hermes:
    tags: [x-twitter, parser, grok, autoreg, gateway, x_search]
    related_skills: [xai-grok-console-registration, ai-provider-autoreg, x-content-advisor]
---

# Grok X-Parser Farm

Free Twitter/X parsing pipeline: autoreg Grok accounts → grok2api gateway pool → live X search.
Full workflow verified end-to-end 2026-09-20. Repo: MeshFinancial/grok-x-farm.

## When to use

- Need real X posts (handle/date/text/likes/URL) without paying Twitter API $200/mo
- Scaling a free Grok model pool for chat/search/image
- Monitoring X for keywords continuously

## Local deployment (this machine)

- Gateway: `C:\Users\User\grok2api-deploy\grok2api\grok2api.exe` on :8000 (proc alive; restart: run binary with `--config config.yaml`)
- Admin creds: `C:\Users\User\grok2api-deploy\SECRETS.local.txt`
- Client key: `C:\Users\User\grok2api-deploy\g2a_key.txt` (`g2a_7c502f8386fc_...`)
- Autoreg: `C:\Users\User\grok-reg\grok-auto` (curl_cffi==0.13.0 pinned, patchright chromium installed)
- Parser: `C:\Users\User\grok2api-deploy\x_parser.py`, replenish: `replenish.py`
- Pool: 2 accounts (t857bjmrgg@sunix.eu.org, u1xqiqhgmy@chato.eu.org) × Web+Build = 4 records, 9 models

## Parse X — the ONLY working method

```python
# Web pool + prompt-based live search. NOT tools:[{type:x_search}] — Build upstream
# has no server-side search (num_server_side_tools_used always 0).
POST http://127.0.0.1:8000/v1/chat/completions
Authorization: Bearer g2a_xxx
{"model": "grok-chat-fast",
 "messages": [{"role":"user","content":"Use your live X search. Find N most recent posts about QUERY from last D days. Reply ONLY with JSON array: [{handle,date,text,likes,url}]"}]}
```

Speed 8-10s, ~500 tokens. Verify results via `api.fxtwitter.com/{user}/status/{id}`.

## Replenish pool

```bash
cd C:\Users\User\grok2api-deploy && python replenish.py --count 5
# reg (tmail + free Turnstile) → import SSO → convert Web→Build; idempotent via imported_sso.txt
```

Turnstile solved FREE: patchright + manual turnstile.render, sitekey `0x4AAAAAAAhr9JGVDZbrZOo0`. ~141-210s/account.

## Pitfalls (all hit in practice)

1. curl_cffi 0.14+ broken on Windows → pin 0.13.0
2. RU egress geo-blocked by xAI → US/EU residential or clean DC
3. Signup page in RU breaks AaronL725 selectors → patch Russian variants into `registration_browser.py` scoreEntry (2 places)
4. credentialEncryptionKey must be base64(32 bytes) — `openssl rand -base64 32`
5. CPA refresh tokens die ~1 month (invalid_grant); SSO stays alive → import by SSO
6. Web→Build conversion unlocks grok-4.5/4.6: `POST /api/admin/v1/accounts/web/convert-to-build {"all":true,"strategy":"missing"}`
7. Gateway 502 transient → retry with backoff (x_parser.py has 3 attempts built in)

## Admin API cheatsheet

```
POST /api/admin/v1/auth/login                   {"username","password"} → data.tokens.accessToken
POST /api/admin/v1/accounts/web/import          multipart file=<SSO text>
POST /api/admin/v1/accounts/web/convert-to-build
POST /api/admin/v1/client-keys                  {"name":"x"} → data.secret (g2a_...)
GET  /v1/models                                 Bearer g2a_...
```
