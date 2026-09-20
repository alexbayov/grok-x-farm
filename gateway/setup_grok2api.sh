#!/usr/bin/env bash
# setup_grok2api.sh — build & configure grok2api gateway from source
# Requirements: Go 1.22+, curl, unzip
set -e

INSTALL_DIR="${G2A_DIR:-$HOME/grok2api}"
mkdir -p "$INSTALL_DIR" && cd "$INSTALL_DIR"

if [ ! -d grok2api ]; then
  echo "[*] downloading chenyme/grok2api..."
  curl -sL -o g2a.zip https://codeload.github.com/chenyme/grok2api/zip/refs/heads/main
  unzip -q g2a.zip && rm g2a.zip && mv grok2api-main grok2api
fi

cd grok2api
[ -f config.yaml ] || cp config.example.yaml config.yaml

if grep -q "replace-with" config.yaml; then
  echo "[*] generating secrets..."
  JWT=$(head -c 32 /dev/urandom | xxd -p -c 64)
  # credentialEncryptionKey MUST be base64 of exactly 32 bytes
  CRED=$(head -c 32 /dev/urandom | base64)
  ADMIN_PW=$(head -c 12 /dev/urandom | base64 | tr -d '/+=' | head -c 20)
  python3 - "$JWT" "$CRED" "$ADMIN_PW" <<'EOF' || {
import sys, re
jwt, cred, pw = sys.argv[1:4]
p = 'config.yaml'
t = open(p, encoding='utf-8').read()
t = re.sub(r'jwtSecret: "[^"]*"', f'jwtSecret: "{jwt}"', t)
t = re.sub(r'credentialEncryptionKey: "[^"]*"', f'credentialEncryptionKey: "{cred}"', t)
t = re.sub(r'(bootstrapAdmin:(?s).{0,200}?password: )"[^"]*"', rf'\1"{pw}"', t)
open(p, 'w', encoding='utf-8').write(t)
EOF
  sed -i "s|replace-with-at-least-32-characters|$JWT|; s|replace-with-base64-key|$CRED|; s|replace-with-a-strong-password|$ADMIN_PW|" config.yaml
  }
  echo "admin password: $ADMIN_PW" >> "$INSTALL_DIR/SECRETS.local.txt"
  echo "jwtSecret: $JWT" >> "$INSTALL_DIR/SECRETS.local.txt"
  echo "credentialEncryptionKey: $CRED" >> "$INSTALL_DIR/SECRETS.local.txt"
  echo "[+] secrets written to $INSTALL_DIR/SECRETS.local.txt (keep private!)"
fi

echo "[*] building (takes ~5-10 min first time)..."
cd backend && go build -o ../grok2api$( [ "$(uname -o)" = "Msys" ] && echo .exe ) ./cmd/grok2api
cd ..

echo "[*] starting gateway on 127.0.0.1:8000 ..."
BIN=./grok2api$( [ "$(uname -o)" = "Msys" ] && echo .exe )
nohup "$BIN" --config "$PWD/config.yaml" > gateway.log 2>&1 &
sleep 8
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/healthz || true)
if [ "$CODE" = "200" ]; then
  echo "[+] GATEWAY UP: http://127.0.0.1:8000 (healthz 200)"
  echo "[+] admin UI: http://127.0.0.1:8000 — login admin / (see SECRETS.local.txt)"
else
  echo "[!] healthz=$CODE — check gateway.log"
  tail -5 gateway.log
fi
