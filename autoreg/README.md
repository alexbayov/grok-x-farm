# Autoreg

Two upstream tools are supported. Both solve Cloudflare Turnstile **for free** (patchright browser + manual widget render, sitekey `0x4AAAAAAAhr9JGVDZbrZOo0`).

## Option A — AaronL725/grok-register (recommended, active)

```bash
git clone https://github.com/AaronL725/grok-register
cd grok-register
uv sync && uv run patchright install chromium
cp config.example.json config.json
```

Minimal `config.json`:

```json
{
  "email_provider": "duckmail",
  "duckmail_api_key": "",
  "register_count": 5,
  "proxy_mode": "auto",
  "proxy": "",
  "multi_thread_enabled": false,
  "enable_nsfw": false,
  "sso_risk_gate_enabled": true,
  "cpa_export_enabled": false
}
```

Run: `python grok_register_ttk.py` (GUI) or `cli` mode.

**Output:** `accounts_*.txt` — one `email:password:SSO` per line.

### RU-locale patch (required if signup page renders in Russian)

Selectors in `registration_browser.py` score buttons by English/Chinese text only.
Add Russian variants to `scoreEntry()` (two places in the file):

```js
const lowerRu = compact.toLowerCase();
if (lowerRu.includes('продолжитьсemail') || lowerRu.includes('продолжитьсэлектроннойпочтой')) return 98;
if (lowerRu.includes('сemail') || lowerRu.includes('черезemail') || lowerRu.includes('электронн') || lowerRu.includes('почт')) return 85;
```

## Option B — grok-auto (archived variant from Vlad's zip)

Same flow + automatic SSO→CPA PKCE minting after each account.
`grok_auto.py --count N --email-provider tmail`.

**Pitfall:** pin `curl_cffi==0.13.0` — 0.14+ is broken on Windows (`No module named 'curl_cffi._wrapper'`).

## After registration → gateway

```bash
python replenish.py --import-only        # import all new SSO into grok2api + convert to Build
# or full cycle:
python replenish.py --count 5            # reg 5 + import + convert
```

`replenish.py` config via env:
- `REG_DIR` — path to grok-auto clone (default `C:\Users\User\grok-reg\grok-auto`)
- `G2A_BASE` — gateway URL (default `http://127.0.0.1:8000`)
- `SECRETS_FILE` — path to file containing `admin password: ...` line

Marker file `imported_sso.txt` makes re-runs idempotent.

## Limits & geo

- ~141–210s per account, single thread (Turnstile serializes on shared browser)
- **RU egress = geo-block.** Need US/EU residential or clean datacenter IP
- Fresh email domains work: `sunix.eu.org`, `chato.eu.org`, `niceground.shop` (tmail/duckmail pools)
