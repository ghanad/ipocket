#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-s1.itleaderman.org}"
PATH_="${2:-/ali}"
ITER="${3:-20}"
SLEEP_SECS="${4:-2}"

URL="https://${DOMAIN}${PATH_}"

echo "[*] Target: $URL"
echo "[*] Iterations: $ITER | sleep: ${SLEEP_SECS}s"
echo

for i in $(seq 1 "$ITER"); do
  echo "===== [$i/$ITER] $(date '+%F %T') ====="

  echo "--- DNS (system) ---"
  # سیستم دی‌ان‌اس که مک واقعاً استفاده می‌کنه:
  scutil --dns | awk '/nameserver\[[0-9]+\]/{print "NS: "$3; exit}' || true

  echo "--- DNS (A/AAAA via dig if exists) ---"
  if command -v dig >/dev/null 2>&1; then
    (dig +short A "$DOMAIN" || true) | sed 's/^/A: /'
    (dig +short AAAA "$DOMAIN" || true) | sed 's/^/AAAA: /'
  else
    echo "dig not found (ok)"
  fi

  echo "--- TLS ---"
  echo | openssl s_client -servername "$DOMAIN" -connect "${DOMAIN}:443" -brief 2>/dev/null | sed 's/^/TLS: /' || echo "TLS: failed"

  echo "--- WS Handshake (curl) ---"
  RESP="$(curl -sk -o /dev/null -D - \
    -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: SGVsbG9Xb3JsZA==" \
    "$URL" || true)"

  STATUS="$(echo "$RESP" | head -n 1 | tr -d '\r')"
  CFRAY="$(echo "$RESP" | tr -d '\r' | awk -F': ' 'tolower($1)=="cf-ray"{print $2}' | head -n1)"
  echo "STATUS: ${STATUS:-no response}"
  echo "CF-RAY: ${CFRAY:-n/a}"

  if ! echo "$STATUS" | grep -q "101"; then
    echo "--- Headers (non-101) ---"
    echo "$RESP" | sed 's/^/H: /'
  fi

  echo
  sleep "$SLEEP_SECS"
done
