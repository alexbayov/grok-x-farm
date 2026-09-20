# grok-x-farm

**Free Twitter/X parser built on a self-replenishing Grok account farm.**
Zero API costs: autoreg → gateway pool → live X search. Full workflow tested end-to-end on 2026-09-20.

Twitter API costs $200/mo. Grok has built-in live X search and returns real posts (handle, date, text, likes, URL) for free. This repo is the complete pipeline:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  AUTOREG    │ ──► │  SSO tokens  │ ──► │  grok2api   │ ──► │  X PARSER    │
│  grok-auto  │     │ accounts.txt │     │  gateway    │     │  x_parser.py │
│  (free      │     │              │     │  :8000      │     │  (JSON out)  │
│  Turnstile) │     │              │     │  OpenAI API │     │              │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
        ▲                                      │
        └──────── replenish.py ────────────────┘
                (reg → import → convert, idempotent)
```

## Components

| Dir | What | Status |
|-----|------|--------|
| `autoreg/` | `replenish.py` — reg N accounts → auto-import SSO into gateway → auto-convert Web→Build | ✅ tested (2 accounts, 141–210s each) |
| `gateway/` | `setup_grok2api.sh` — build chenyme/grok2api from source (Go), config with generated secrets | ✅ tested (healthz 200, 9 models) |
| `parser/` | `x_parser.py` — CLI X parser with retry, JSON output | ✅ tested (posts verified via fxtwitter 4/4) |
| `workflow/` | `GUIDE_RU.md` — full step-by-step guide with proofs | ✅ |
| `skill/` | `SKILL.md` — Hermes Agent skill for this pipeline | ✅ |

## Quick start

```bash
# 1. Gateway (needs Go 1.22+, or use official Docker image)
bash gateway/setup_grok2api.sh          # → http://127.0.0.1:8000, secrets in SECRETS.local.txt

# 2. Autoreg tooling (Python 3.12+, uv)
git clone https://github.com/AaronL725/grok-register autoreg/grok-register
cd autoreg/grok-register && uv sync && uv run patchright install chromium
cp .env.example .env                     # EMAIL_PROVIDER=tmail, GROK_PROXY= (empty)

# 3. Farm: reg 5 accounts → auto-import → convert to Build
python autoreg/replenish.py --count 5

# 4. Parse X
export G2A_KEY=g2a_xxx                   # from gateway admin → Client Keys
python parser/x_parser.py "your query" --days 3 --max 10 --json out.json
```

## How X parsing actually works (important)

`tools: [{"type": "x_search"}]` via the gateway **does not work** — the Build upstream has no
server-side search (`num_server_side_tools_used: 0` in every test). The working path:

- Model: **`grok-chat-fast`** (Web pool)
- Prompt: `Use your live X search. Find N most recent posts about QUERY from last D days. Reply ONLY with JSON array: [{handle,date,text,likes,url}]`
- Web pool has native live X search built in; the model returns real posts with URLs and like counts
- Speed: 8–10s per query, ~500 tokens
- Verify results via `api.fxtwitter.com/{user}/status/{id}` — matched 4/4 in our tests

## Key pitfalls (all hit in practice)

1. **`curl_cffi` must be pinned to 0.13.0** on Windows — 0.14+ ships broken `_wrapper`
2. **Turnstile is solved free** via patchright + manual `turnstile.render` (sitekey `0x4AAAAAAAhr9JGVDZbrZOo0`) — no 2captcha/YesCaptcha needed
3. **RU egress IPs are geo-blocked by xAI** — need US/EU residential or clean DC
4. **Registration page may render in Russian** — AaronL725's selectors only match en/zh; patch `registration_browser.py` with Russian button-text variants (see workflow guide)
5. **CPA refresh tokens die in ~1 month** (`invalid_grant`), but SSO tokens stay alive — import via SSO
6. **grok2api `credentialEncryptionKey` must be base64 of exactly 32 bytes** — `openssl rand -base64 32`, not urlsafe random string
7. **Web→Build conversion** (`POST /api/admin/v1/accounts/web/convert-to-build`) unlocks grok-4.5/4.6 routes

## Gateway admin API cheatsheet

```
POST /api/admin/v1/auth/login                    {"username","password"} → accessToken
POST /api/admin/v1/accounts/web/import           multipart file=SSO text
POST /api/admin/v1/accounts/web/convert-to-build {"all":true,"strategy":"missing"}
POST /api/admin/v1/client-keys                   {"name":"x-parser"} → g2a_xxx secret
GET  /v1/models                                  (client key auth) → serviceable models
POST /v1/chat/completions                        OpenAI-compatible inference
```

## Verified proof run (2026-09-20)

- gateway built from source: `grok2api.exe` 90MB, healthz 200
- 2 accounts registered from scratch: Turnstile solved free (752-char token), 141s & 210s
- import: `created:1 synced:1` ×2; Web→Build: `created:1` ×2 → 4 pool records, 9 models
- chat test: `GATEWAY_OK`
- X parse test: 5 real posts about 'grok api' + 4 posts about 'smm panel telegram bot' → JSON
- fxtwitter verification: 4/4 posts real, text and likes match 1:1

## Credits / upstream

- Gateway: [chenyme/grok2api](https://github.com/chenyme/grok2api) (MIT, 7.7k★)
- Autoreg core: [AaronL725/grok-register](https://github.com/AaronL725/grok-register) (MIT, 2.2k★) + archived `grok-auto` variant with free Turnstile solver
- X Search docs: [docs.x.ai/developers/tools/x-search](https://docs.x.ai/developers/tools/x-search)

## Disclaimer

Research/educational use. Mass registration may violate xAI ToS; accounts can be banned. Your responsibility.
