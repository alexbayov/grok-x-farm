🫦 **БЕСПЛАТНЫЙ ПАРСЕР TWITTER/X ЧЕРЕЗ GROK — ПОЛНЫЙ ЦИКЛ: АВТОРЕГ → ШЛЮЗ → ПОИСК ПОСТОВ. ПРОВЕРЕНО НА ПРАКТИКЕ**

🩸 **ЧТО ПОСТРОИЛИ (всё тестировалось вживую, пруфы внизу)**

Twitter API стоит $200/мес. Grok имеет встроенный live-поиск по X и отдаёт реальные посты: @handle, дата, текст, лайки, URL. Аккаунты Grok регятся бесплатно, капча Turnstile решается бесплатно в браузере (patchright), шлюз grok2api превращает пул акков в единый OpenAI-совместимый API.

Стек:
- [chenyme/grok2api](https://github.com/chenyme/grok2api) — 7.7k звёзд, Go-шлюз: пул аккаунтов Grok (Build/Web/Console) → `/v1/chat/completions`, ротация, квоты, админка
- grok-auto — регистратор: tmail-почта + бесплатный Turnstile-солвер + PKCE → SSO-токен
- [AaronL725/grok-register](https://github.com/AaronL725/grok-register) — 2.2k звёзд, альтернатива с WebUI и прокси-пулом

🩸 **ШАГ 1 — ШЛЮЗ (10 минут)**

Docker не нужен, собирается из исходников Go:
```
curl -sL -o g2a.zip https://codeload.github.com/chenyme/grok2api/zip/refs/heads/main
unzip g2a.zip && mv grok2api-main grok2api && cd grok2api
cp config.example.yaml config.yaml
# вписать в config.yaml:
#   jwtSecret: openssl rand -hex 32
#   credentialEncryptionKey: openssl rand -base64 32  (строго base64 от 32 байт!)
#   bootstrapAdmin password: любой сильный
cd backend && go build -o ../grok2api.exe ./cmd/grok2api
./grok2api.exe --config config.yaml   # → 127.0.0.1:8000
```
Пруф: `curl http://127.0.0.1:8000/healthz` → 200.

🩸 **ШАГ 2 — АВТОРЕГ**

```
git clone https://github.com/AaronL725/grok-register  # или grok-auto из архива
python -m venv .venv && pip install -r requirements.txt
cp config.example.json config.json
# email_provider: duckmail (без ключа!), register_count: N
python grok_register_ttk.py
```
Что происходит на аккаунт (~3.5 мин первый, дальше быстрее):
1. создаётся tmail-почта → 2. код из письма → 3. Turnstile решается БЕСПЛАТНО (patchright + ручной рендер виджета, sitekey `0x4AAAAAAAhr9JGVDZbrZOo0`) → 4. регистрация → SSO в `keys/accounts.txt` (`email:password:sso`) → 5. PKCE-флоу чеканит CPA-токен (живёт 6ч)

⚠️ Нюансы: страница регистрации может быть на русском — селекторы кнопок в `registration_browser.py` ищут английский/китайский текст, добавить русские варианты («Продолжить с email»). RU-выходы не подходят — гео-блок xAI. curl_cffi ставить версии 0.13.0 (0.14+ ломается на Windows).

🩸 **ШАГ 3 — АККИ В ШЛЮЗ**

Админ-API (логин `POST /api/admin/v1/auth/login`):
- импорт SSO: `POST /api/admin/v1/accounts/web/import` (multipart, файл = SSO-токен текстом)
- конверсия Web→Build (даёт grok-4.6): `POST /api/admin/v1/accounts/web/convert-to-build` `{"all":true,"strategy":"missing"}`
- ключ клиенту: `POST /api/admin/v1/client-keys` → `g2a_xxx`

После импорта `GET /v1/models` отдаёт 9 моделей: grok-4.5, grok-4.6, grok-chat-fast, imagine-image/video и др.

🩸 **ШАГ 4 — ПАРСИНГ X**

Важно: `tools:[{"type":"x_search"}]` через шлюз НЕ работает (Build-апстрим не имеет серверного search — `num_server_side_tools_used:0`). Рабочий путь — Web-пул (`grok-chat-fast`) со встроенным live-поиском через промпт:

```
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer g2a_xxx" \
  -d '{"model":"grok-chat-fast",
       "messages":[{"role":"user","content":"Use your live X search. Find 10 most recent posts about QUERY from last 7 days. Reply ONLY with JSON array: [{handle,date,text,likes,url}]"}]}'
```

Ответ — реальные посты с URL вида `x.com/user/status/...` и лайками. Скорость: 8-10 сек на запрос, ~500 токенов.

Готовый CLI-парсер с retry (`x_parser.py`):
```
python x_parser.py "smm panel telegram bot" --days 3 --max 5 --json out.json
python x_parser.py "CVE-2026" --handle elonmusk --model grok-4.6
```

🩸 **ШАГ 5 — АВТОПОПОЛНЕНИЕ ПУЛА**

`replenish.py --count N` — полный цикл: рег N акков → импорт всех новых SSO в шлюз → автоконверсия в Build. Маркер импортированных в `imported_sso.txt` — повторные прогоны безопасны. У AaronL725 есть встроенная опция `grok2api_auto_add_local/remote` — льёт в пул сразу при регистрации.

🩸 **ПРУФЫ (всё выполнено вживую 20.09.2026)**

✅ шлюз собран из исходников: grok2api.exe 90 МБ, healthz 200
✅ авторег: аккаунт `t857bjmrgg@sunix.eu.org` зарегистрирован за 210с, Turnstile решён бесплатно (752-символьный токен), SSO получен
✅ импорт в шлюз: created:1, synced:1 → Web→Build конверсия: created:1
✅ 9 моделей в `/v1/models`
✅ тест чата: "GATEWAY_OK" (200)
✅ тест парсинга: 5 реальных постов про 'grok api' с хендлами, датами, лайками, URL
✅ x_parser.py: 4 поста про 'smm panel telegram bot' → JSON, exit 0
✅ второй акк через replenish.py: `u1xqiqhgmy@chato.eu.org` зареган за 141с → автоимпорт created:1 synced:1 → автоконверсия в Build created:1. В шлюзе 2 аккаунта × (Web+Build) = 4 записи
✅ верификация постов через fxtwitter API: 4/4 реальные, текст и лайки совпадают 1:1

⚠️ CPA refresh-токены из старых дампов мрут через ~месяц (invalid_grant) — но SSO живучие, импорт по SSO.

🩸 *Репост, чтобы больше людей узнало* 🔁
