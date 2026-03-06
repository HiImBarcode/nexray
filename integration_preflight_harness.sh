#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ENTITY_ID="${ENTITY_ID:-ent-03}"
PLATFORMS=(shopify tiktokshop lazada)

# Login
login_payload='{"username":"admin","password":"admin"}'
login_resp=$(curl -sS -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "$login_payload")

token=$(python3 -c 'import sys,json; print(json.loads(sys.stdin.read() or "{}").get("token", ""))' <<< "$login_resp")

if [ -z "$token" ]; then
  echo "[FAIL] Login failed"
  echo "$login_resp"
  exit 1
fi

echo "[OK] Login successful"

echo "\n=== Running stub preflight (no live API calls) ==="
for platform in "${PLATFORMS[@]}"; do
  echo "\n--- $platform ---"

  create_resp=$(curl -sS -X POST "$BASE_URL/api/channels" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d "{\"entity_id\":\"$ENTITY_ID\",\"channel_type\":\"$platform\",\"shop_name\":\"$platform preflight\",\"shop_url\":\"https://example.local/$platform\",\"region\":\"PH\",\"api_key\":\"stub-$platform\"}")

  channel_id=$(python3 -c 'import sys,json; print(json.loads(sys.stdin.read() or "{}").get("id", ""))' <<< "$create_resp")

  if [ -z "$channel_id" ]; then
    echo "[FAIL] create channel for $platform"
    echo "$create_resp"
    continue
  fi

  sync_resp=$(curl -sS -X POST "$BASE_URL/api/channels/$channel_id/sync_orders" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d '{}')

  push_resp=$(curl -sS -X POST "$BASE_URL/api/channels/$channel_id/push_inventory" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d '{}')

  sync_ok=$(python3 -c 'import sys,json; o=json.loads(sys.stdin.read() or "{}"); print("yes" if o.get("success") is True and o.get("stub") is True else "no")' <<< "$sync_resp")
  push_ok=$(python3 -c 'import sys,json; o=json.loads(sys.stdin.read() or "{}"); print("yes" if o.get("success") is True and o.get("stub") is True else "no")' <<< "$push_resp")

  echo "channel_id: $channel_id"
  echo "sync_ok: $sync_ok | sync_resp: $sync_resp"
  echo "push_ok: $push_ok | push_resp: $push_resp"

done

echo "\n[INFO] Stub preflight complete. If using live credentials, point app code to real adapters and then assert real order IDs/webhook verification."