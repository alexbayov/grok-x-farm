#!/usr/bin/env bash
# setup-tunnel.sh —一键部署 Grok Farm туннель на любой комп
# Запуск: curl -fsSL https://raw.githubusercontent.com/alexbayov/grok-x-farm/main/setup-tunnel.sh | bash
# Или: bash setup-tunnel.sh
#
# Что делает:
# 1. Проверяет/создаёт SSH-ключ к серверу
# 2. Поднимает SSH-туннель localhost:8000 → сервер
# 3. Проверяет что гейтвей отвечает
# 4. Настраивает OpenCode (если установлен)
# 5. Настраивает Zed (если установлен)
# 6. Делает туннель автозапуска через systemd (переживает ребут)

set -euo pipefail

# ── КОНФИГ ──────────────────────────────────────────────
SERVER_IP="159.195.23.79"
SERVER_USER="root"
GATEWAY_PORT=8000
GROK_KEY="g2a_03ebed34ac25_3QSOIbCC0-8Lxi9OZowleGWK3LkPN_GR"
GROK_BASE="http://localhost:${GATEWAY_PORT}/v1"
SSH_PORT=22
# ────────────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}ℹ${NC}  $1"; }
ok()    { echo -e "${GREEN}✓${NC}  $1"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $1"; }
err()   { echo -e "${RED}✗${NC}  $1"; }

echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  🩸 GROK FARM — TUNNEL SETUP${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""

# ── 1. ПРОВЕРКА ОС ────────────────────────────────────────
OS_TYPE="$(uname -s)"
info "OS: ${OS_TYPE} $(uname -r)"

if [[ "$OS_TYPE" == "Darwin" ]]; then
    CONFIG_DIR="$HOME/.config/opencode"
    ZED_DIR="$HOME/.config/zed"
    SERVICE_DIR="$HOME/Library/LaunchAgents"
    SERVICE_NAME="com.grok-farm.tunnel"
    IS_MAC=1
elif [[ "$OS_TYPE" == "Linux" ]]; then
    CONFIG_DIR="$HOME/.config/opencode"
    ZED_DIR="$HOME/.config/zed"
    SERVICE_DIR="$HOME/.config/systemd/user"
    SERVICE_NAME="grok-farm-tunnel"
    IS_MAC=0
else
    err "Unsupported OS: $OS_TYPE"
    exit 1
fi

# ── 2. SSH-КЛЮЧ ───────────────────────────────────────────
SSH_KEY="$HOME/.ssh/grok_farm_key"

if [[ -f "$SSH_KEY" ]]; then
    ok "SSH-ключ найден: $SSH_KEY"
else
    info "Создаю SSH-ключ..."
    mkdir -p "$HOME/.ssh"
    ssh-keygen -t ed25519 -f "$SSH_KEY" -N "" -C "grok-farm-tunnel" -q
    ok "SSH-ключ создан: $SSH_KEY"
fi

# Добавляем ключ в ssh config для сервера
SSH_CONFIG_ENTRY="Host grok-farm
    HostName ${SERVER_IP}
    User ${SERVER_USER}
    Port ${SSH_PORT}
    IdentityFile ${SSH_KEY}
    StrictHostKeyChecking no
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ExitOnForwardFailure yes"

if grep -q "grok-farm" "$HOME/.ssh/config" 2>/dev/null; then
    ok "SSH config уже настроен"
else
    info "Добавляю запись в ~/.ssh/config..."
    echo "" >> "$HOME/.ssh/config"
    echo "$SSH_CONFIG_ENTRY" >> "$HOME/.ssh/config"
    ok "SSH config обновлён"
fi
chmod 600 "$HOME/.ssh/config"

# ── 3. ДОБАВЛЕНИЕ КЛЮЧА НА СЕРВЕР ─────────────────────────
info "Проверяю доступ к серверу..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes grok-farm "echo ok" 2>/dev/null | grep -q ok; then
    ok "SSH-доступ работает"
else
    warn "Нужен пароль для первой установки ключа на сервер"
    info "Копирую ключ на сервер (введите пароль root@${SERVER_IP}):"
    if ssh-copy-id -i "${SSH_KEY}.pub" -p "${SSH_PORT}" "${SERVER_USER}@${SERVER_IP}"; then
        ok "Ключ установлен на сервер"
    else
        err "Не удалось установить ключ. Проверьте пароль/доступ."
        echo ""
        info "Можно вручную: ssh-copy-id -i ${SSH_KEY}.pub ${SERVER_USER}@${SERVER_IP}"
        exit 1
    fi
fi

# ── 4. УБИВАЕМ СТАРЫЙ ТУННЕЛЬ ──────────────────────────────
info "Останавливаю старый туннель (если есть)..."
if [[ $IS_MAC -eq 1 ]]; then
    launchctl unload "${SERVICE_DIR}/${SERVICE_NAME}.plist" 2>/dev/null || true
else
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
fi
pkill -f "ssh.*grok-farm.*-L.*${GATEWAY_PORT}" 2>/dev/null || true
ok "Старый туннель остановлен"

# ── 5. ПОДНИМАЕМ ТУННЕЛЬ ──────────────────────────────────
info "Поднимаю SSH-туннель..."
ssh -fN grok-farm -L "${GATEWAY_PORT}:127.0.0.1:${GATEWAY_PORT}" 2>/dev/null || {
    err "Не удалось поднять туннель"
    exit 1
}
sleep 2

# ── 6. ПРОВЕРКА ГЕЙТВЕЯ ───────────────────────────────────
info "Проверяю гейтвей..."
HEALTH=$(curl -s --connect-timeout 5 "http://localhost:${GATEWAY_PORT}/healthz" 2>/dev/null || echo "FAIL")

if [[ "$HEALTH" == *'"ok":true'* ]]; then
    ok "Гейтвей жив! ${HEALTH}"
else
    err "Гейтвей не отвечает: $HEALTH"
    warn "Возможно туннель упал или гейтвей не запущен на сервере"
    exit 1
fi

# Проверяем модели
MODELS=$(curl -s "http://localhost:${GATEWAY_PORT}/v1/models" \
    -H "Authorization: Bearer ${GROK_KEY}" 2>/dev/null || echo "FAIL")

if [[ "$MODELS" == *"grok-4.7"* ]]; then
    ok "Модели доступны: grok-4.7, grok-chat-fast и др."
else
    warn "Не удалось получить список моделей"
fi

# ── 7. AUTOSTART (systemd / launchd) ─────────────────────
info "Настраиваю автозапуск туннеля..."

if [[ $IS_MAC -eq 1 ]]; then
    # macOS — launchd plist
    mkdir -p "$SERVICE_DIR"
    cat > "${SERVICE_DIR}/${SERVICE_NAME}.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/ssh</string>
        <string>-N</string>
        <string>-L</string>
        <string>${GATEWAY_PORT}:127.0.0.1:${GATEWAY_PORT}</string>
        <string>grok-farm</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/grok-farm-tunnel.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/grok-farm-tunnel.out</string>
</dict>
</plist>
PLIST
    launchctl load "${SERVICE_DIR}/${SERVICE_NAME}.plist" 2>/dev/null || true
    ok "Автозапуск настроен (launchd)"
else
    # Linux — systemd user service
    mkdir -p "$SERVICE_DIR"
    cat > "${SERVICE_DIR}/${SERVICE_NAME}.service" << SERVICE
[Unit]
Description=Grok Farm SSH Tunnel
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/ssh -N -L ${GATEWAY_PORT}:127.0.0.1:${GATEWAY_PORT} grok-farm
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
SERVICE
    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user start "$SERVICE_NAME" 2>/dev/null || true
    ok "Автозапуск настроен (systemd)"
fi

# ── 8. OPENCODE ──────────────────────────────────────────
if command -v opencode &>/dev/null || [[ -d "$CONFIG_DIR" ]]; then
    info "OpenCode найден, настраиваю..."
    mkdir -p "$CONFIG_DIR"
    CONFIG_FILE="$CONFIG_DIR/opencode.json"

    if [[ -f "$CONFIG_FILE" ]]; then
        # Добавляем grok в существующий конфиг
        python3 -c "
import json, sys, os

path = os.path.expanduser('$CONFIG_FILE')
with open(path, 'r') as f:
    config = json.load(f)

if 'provider' not in config:
    config['provider'] = {}

config['provider']['grok'] = {
    'npm': '@ai-sdk/openai-compatible',
    'name': 'Grok Farm (free, 26 accs pool)',
    'options': {
        'baseURL': '${GROK_BASE}',
        'apiKey': '${GROK_KEY}'
    },
    'models': {
        'grok-4.7': {'name': 'Grok 4.7'},
        'grok-chat-fast': {'name': 'Grok Chat Fast'},
        'grok-composer-2.5-fast': {'name': 'Grok Composer 2.5 Fast'},
        'grok-imagine-image': {'name': 'Grok Imagine Image'},
        'grok-imagine-image-2.0': {'name': 'Grok Imagine Image 2.0'}
    }
}

with open(path, 'w') as f:
    json.dump(config, f, indent=2)

print('OK')
" 2>/dev/null && ok "OpenCode настроен" || warn "Не удалось настроить OpenCode (ручками)"
    else
        # Создаём новый конфиг
        cat > "$CONFIG_FILE" << OCODE
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "grok/grok-4.7",
  "provider": {
    "grok": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Grok Farm (free, 26 accs pool)",
      "options": {
        "baseURL": "${GROK_BASE}",
        "apiKey": "${GROK_KEY}"
      },
      "models": {
        "grok-4.7": {"name": "Grok 4.7"},
        "grok-chat-fast": {"name": "Grok Chat Fast"},
        "grok-composer-2.5-fast": {"name": "Grok Composer 2.5 Fast"},
        "grok-imagine-image": {"name": "Grok Imagine Image"},
        "grok-imagine-image-2.0": {"name": "Grok Imagine Image 2.0"}
      }
    }
  }
}
OCODE
        ok "OpenCode конфиг создан"
    fi
else
    warn "OpenCode не установлен — пропуск"
fi

# ── 9. ZED ────────────────────────────────────────────────
if [[ -d "$HOME/.local/zed.app" ]] || [[ -d "/Applications/Zed.app" ]] || [[ -d "$ZED_DIR" ]]; then
    info "Zed найден, настраиваю..."
    mkdir -p "$ZED_DIR"
    ZED_FILE="$ZED_DIR/settings.json"

    if [[ -f "$ZED_FILE" ]]; then
        python3 -c "
import json, re, os

path = os.path.expanduser('$ZED_FILE')
with open(path, 'r') as f:
    content = f.read()

content = re.sub(r'//.*', '', content)
content = re.sub(r',\s*([}\]])', r'\1', content)
config = json.loads(content)

if 'agent' not in config:
    config['agent'] = {}
if 'model_parameters' not in config['agent']:
    config['agent']['model_parameters'] = []

config['agent']['model_parameters'] = [
    m for m in config['agent']['model_parameters']
    if not m.get('name', '').startswith('Grok')
]

grok_models = [
    {
        'provider': 'openai',
        'api_url': '${GROK_BASE}',
        'api_key': '${GROK_KEY}',
        'model_name': 'grok-4.7',
        'name': 'Grok 4.7',
        'max_tokens': 8192
    },
    {
        'provider': 'openai',
        'api_url': '${GROK_BASE}',
        'api_key': '${GROK_KEY}',
        'model_name': 'grok-chat-fast',
        'name': 'Grok Chat Fast',
        'max_tokens': 8192
    }
]
config['agent']['model_parameters'].extend(grok_models)

with open(path, 'w') as f:
    json.dump(config, f, indent=2)

print('OK')
" 2>/dev/null && ok "Zed настроен" || warn "Не удалось настроить Zed"
    else
        cat > "$ZED_FILE" << ZEDCFG
{
  "agent": {
    "model_parameters": [
      {
        "provider": "openai",
        "api_url": "${GROK_BASE}",
        "api_key": "${GROK_KEY}",
        "model_name": "grok-4.7",
        "name": "Grok 4.7",
        "max_tokens": 8192
      },
      {
        "provider": "openai",
        "api_url": "${GROK_BASE}",
        "api_key": "${GROK_KEY}",
        "model_name": "grok-chat-fast",
        "name": "Grok Chat Fast",
        "max_tokens": 8192
      }
    ]
  }
}
ZEDCFG
        ok "Zed конфиг создан"
    fi
else
    warn "Zed не установлен — пропуск"
fi

# ── 10. ИТОГ ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ Готово!${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${BOLD}API:${NC}   http://localhost:${GATEWAY_PORT}/v1"
echo -e "${BOLD}Key:${NC}   ${GROK_KEY}"
echo -e "${BOLD}Туннель:${NC} SSH → ${SERVER_IP} (автозапуск ✅)"
echo ""
echo -e "${BOLD}Модели:${NC}"
echo "  • grok-4.7 (reasoning)"
echo "  • grok-chat-fast (быстрый, live X search)"
echo "  • grok-composer-2.5-fast"
echo "  • grok-imagine-image (генерация фото)"
echo "  • grok-imagine-image-2.0"
echo ""
echo -e "${BOLD}Проверка:${NC} curl http://localhost:${GATEWAY_PORT}/healthz"
echo ""
if command -v opencode &>/dev/null; then
    echo -e "${GREEN}✓${NC} OpenCode — перезапусти, появятся grok-4.7 и grok-chat-fast"
fi
if [[ -d "$HOME/.local/zed.app" ]] || [[ -d "/Applications/Zed.app" ]]; then
    echo -e "${GREEN}✓${NC} Zed — перезапусти, появятся Grok 4.7 и Grok Chat Fast"
fi
echo ""
echo -e "${BOLD}Туннель переживает ребут ✅${NC} (systemd/launchd)"
echo ""
