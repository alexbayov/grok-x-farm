# grok-x-farm

**Free Twitter/X parser built on a self-replenishing Grok account farm.**
Zero API costs: autoreg → gateway pool → live X search. Full workflow tested end-to-end on 2026-09-20.

![grok-x-farm status dashboard](assets/dashboard.png)

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
| `farm.py` | **Unified CLI**: doctor / reg / import / keys / parse / crawl | ✅ tested (doctor ALL OK) |
| `config/` | `farm.config.example.json` — email providers, captcha modes, proxy modes | ✅ |
| `autoreg/` | `replenish.py` + docs — reg accounts, auto-import SSO, auto-convert Web→Build | ✅ tested (3 accounts) |
| `gateway/` | `setup_grok2api.sh` (Linux) + `setup_windows.bat`/`gen_secrets.ps1` (Windows) | ✅ tested |
| `parser/` | `x_parser.py`, `x_crawl_100.py`, `queries.txt`, verified 105-tweet dataset | ✅ tested (fxtwitter 10/10) |
| `workflow/` | `GUIDE_RU.md` — full step-by-step with proofs | ✅ |
| `skill/` | `SKILL.md` — Hermes Agent skill | ✅ |
| `dashboard/` | `panel.py` — local web control panel: live status, start/stop gateway, run reg/crawl, edit config, secrets, log tail. Stdlib only, 127.0.0.1:8010 | ✅ |
| `tests/` | offline self-checks: `python tests/test_parser_offline.py` (6/6) + `python tests/test_panel_offline.py` (7/7) | ✅ 13/13 |
| `AUDIT.md` | Security/reliability audit: 9 fixed + 6 open weaknesses | ✅ |

## Configuration

Copy `config/farm.config.example.json` → `farm.config.json` and edit:

```jsonc
{
  "email":   { "provider": "tmail" },        // tmail|luckmail|mailnest|fce|gptmail|gmail|outlook
  "captcha": { "mode": "free_browser" },     // free_browser ($0, patchright) | yescaptcha (paid fallback)
  "proxy":   { "mode": "direct",             // direct | single | pool
               "single": "",                 // http://user:pass@host:port — NON-RU geo required
               "geo_whitelist": ["US","EU","UA"] },
  "gateway": { "parse_model": "grok-chat-fast",  // Web pool = native live X search
               "tool_model": "grok-4.5" },       // Build pool = function calling
  "parser":  { "posts_per_query": 15, "days_window": 14, "verify_sample_size": 10, "delay_between_queries_sec": 3 }
}
```

Secrets via env (override config): `G2A_KEY`, `G2A_ADMIN_PASS`, `GROK_PROXY`, `YESCAPTCHA_KEY`,
`LUCKMAIL_API_KEY`, `MAILNEST_API_KEY`, `FCE_API_KEY`, `GMAIL_APP_PASSWORD`, `REG_DIR`.

## CLI

```bash
python farm.py doctor                 # gateway + egress geo + pool + models + inference probe
python farm.py reg --count 5          # register → auto-import → auto-convert
python farm.py import                 # import new SSO only (idempotent)
python farm.py keys                   # create client key → g2a_key.txt
python farm.py parse "query" --max 15 --days 7 --json out.json
python farm.py crawl --queries-file parser/queries.txt --target 100 --out tweets.json --state seen.json
                                      # --state: cross-run dedup (output merges all runs)
                                      # + fxtwitter verification of 10 random tweets: exists + date + likes
```

## Control panel

```bash
python dashboard/panel.py            # → http://127.0.0.1:8010 (localhost only, stdlib, no deps)
```

- **Status**: runs `farm.py doctor` (button + auto-refresh 30s)
- **Gateway**: start/stop grok2api (exe path from `gateway.exe_path` / `G2A_EXE` / standard locations)
- **Run**: reg (count 1..20) and crawl (queries file, target, days, state) as background tasks with live log tail
- **Settings**: email provider, captcha mode, proxy mode/single, geo whitelist, parser limits → saved to `farm.config.json` (whitelist + type/range validated)
- **Secrets**: `G2A_KEY`, `YESCAPTCHA_KEY`, etc → stored in `farm.secrets.json` (gitignored, 0600), masked in UI, injected into child-process env — never returned to the browser

## Tool use (Build pool)

Function calling works on grok-4.5/4.6 (Build pool) — verified full cycle:

```bash
curl http://127.0.0.1:8000/v1/chat/completions -H "Authorization: Bearer g2a_xxx" -d '{
  "model": "grok-4.5",
  "messages": [{"role":"user","content":"What is the weather in Tokyo?"}],
  "tools": [{"type":"function","function":{"name":"get_weather",
    "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]
}'
# → finish_reason: tool_calls, arguments {"city":"Tokyo"}
# send tool result back → final answer
```

Note: server-side `x_search` tool does NOT work through the gateway (Build upstream has no
server-side search). X parsing goes through the Web pool prompt path — see parser/README.md.

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
- 2 accounts registered from scratch in this proof run (pool total: 4 accounts / 8 records): Turnstile solved free (752-char token), 141s & 210s
- import: `created:1 synced:1` ×2; Web→Build: `created:1` ×2 → 4 pool records, 9 models
- chat test: `GATEWAY_OK`
- X parse test: 5 real posts about 'grok api' + 4 posts about 'smm panel telegram bot' → JSON
- fxtwitter verification: 4/4 posts real, text and likes match 1:1

### Proof run 2026-09-21 (v2.1, control panel)

- reg 10/10 accounts from scratch (avg 91.4s, Turnstile free) — launched from the web panel
- mass import of all 669 SSO (every one `created:1 synced:1` — the old 655-account stash proved ALIVE), convert Web→Build `created:665`
- pool now **1338 records (web:669, build:669)**; doctor ALL OK; live parse: 3 real posts in 7.4s
- panel-driven crawl ×2: cross-run dedup `+0 new` on repeat query; fxtwitter verify exists/date/likes **10/10/10** both runs (25 tweets accumulated in state)
- interrupted import (expired admin JWT, 401 at #437) resumed via marker with zero duplicates — idempotency proven in production

## Credits / upstream

- Gateway: [chenyme/grok2api](https://github.com/chenyme/grok2api) (MIT, 7.7k★)
- Autoreg core: [AaronL725/grok-register](https://github.com/AaronL725/grok-register) (MIT, 2.2k★) + archived `grok-auto` variant with free Turnstile solver
- X Search docs: [docs.x.ai/developers/tools/x-search](https://docs.x.ai/developers/tools/x-search)

## Disclaimer

Research/educational use. Mass registration may violate xAI ToS; accounts can be banned. Your responsibility.
