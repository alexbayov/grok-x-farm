# X Parser

`x_parser.py` — CLI Twitter/X parser through the local grok2api gateway. Free, no Twitter API.

## Setup

```bash
export G2A_KEY=g2a_xxx        # client key from gateway admin → Client Keys
# or put the key in g2a_key.txt next to the script
export G2A_BASE=http://127.0.0.1:8000   # optional
```

## Usage

```bash
python x_parser.py "carding forum leak" --days 3 --max 5 --json out.json
python x_parser.py "CVE-2026" --handle somedude --model grok-chat-fast
python x_parser.py "smm panel" --days 7 --max 20
```

## Output schema

```json
[
  {
    "handle": "@user",
    "date": "2026-09-20",
    "text": "full post text",
    "likes": 14,
    "url": "https://x.com/user/status/2101229726970818733"
  }
]
```

See `example_output.json` for a real verified run.

## How it works

The Web-pool model (`grok-chat-fast`) has **native live X search**. The parser sends a strict
JSON-format prompt; the model executes a live search and returns real posts. Verified against
`api.fxtwitter.com` — 4/4 posts real, text and like counts match 1:1.

What does NOT work: `tools:[{"type":"x_search"}]` through the gateway. The Build upstream has no
server-side search support (`num_server_side_tools_used: 0`). Don't waste time on that path.

## Verification helper

Always validate harvested posts before using them downstream:

```python
import json, urllib.request
def fx_check(url):
    u, sid = url.replace('https://x.com/', '').split('/status/')
    req = urllib.request.Request(f'https://api.fxtwitter.com/{u}/status/{sid}',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())['tweet']
```

## Scaling

- Each gateway account = independent quota; the gateway rotates accounts automatically
- Client key limits: RPM 120, concurrency 8 by default (adjustable in admin)
- For continuous monitoring run `x_parser.py` on a cron and diff `out.json` against previous run
- Pool replenishment: `python ../autoreg/replenish.py --count 5` when accounts get banned
