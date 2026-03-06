# NEXRAY Integration Preflight Report (Agent 4)

## 1) Repo Audit Findings

- Current implementation is **integration-skeleton/stub mode** for all marketplaces.
- `channel_connections` table exists with fields for `api_key`, `api_secret`, `access_token`, `refresh_token`, but there is no platform service implementation.
- Sync/push endpoints are hardcoded stubs:
  - `POST /api/channels/{channel_id}/sync_orders` returns 3 fake orders.
  - `POST /api/channels/{channel_id}/push_inventory` returns computed local inventory payload.
- No webhook routes exist (`/webhook/*` absent).
- No token management, signature checks, pagination, retry, rate-limit handling, or sandbox/prod endpoint branching.
- Credentials are stored in DB columns named “encrypted” but are currently plain payload.

---

## 2) Preflight Matrix (Current State)

### Shopify

- **Auth method:** Shopify OAuth / Admin API access token (custom app or public app).
- **Required secrets/env (live):**
  - `SHOPIFY_SHOP_DOMAIN` (or shop name)
  - `SHOPIFY_ACCESS_TOKEN` (or API key/secret pair)
  - `SHOPIFY_WEBHOOK_SECRET`
  - `SHOPIFY_API_VERSION`
  - optional: partner/client ID fields for OAuth code flow.
- **Sandbox vs Production endpoint:** **Not implemented** (no env-controlled base URL in repo).
- **Minimal connectivity test:** currently **not possible live**; only stub endpoint.
- **Order fetch test:** only stub data (`STUB-*`).
- **Webhook receive/verify:** not present.
- **Readiness:** Not ready.

### TikTok Shop (`tiktokshop` channel_type)

- **Auth method:** TikTok Shop API auth flow (app key/secret + OAuth/token refresh).
- **Required secrets/env (live):**
  - `TIKTOK_APP_KEY`, `TIKTOK_APP_SECRET`
  - `TIKTOK_AUTH_CODE` / token lifecycle secrets
  - `TIKTOK_SHOP_ID` / seller-id equivalent
  - webhook signing secret + callback URL
- **Sandbox vs Production endpoint:** **Not implemented**.
- **Minimal connectivity test:** currently **not possible live**; only stub endpoint.
- **Order fetch test:** only stub data.
- **Webhook receive/verify:** not present.
- **Readiness:** Not ready.

### Lazada

- **Auth method:** Lazada App signature + token flow (region-specific).
- **Required secrets/env (live):
  - `LAZADA_APP_KEY`, `LAZADA_APP_SECRET`
  - `LAZADA_SELLER_ID`
  - `LAZADA_ACCESS_TOKEN`
  - region + endpoint base + webhook signing secret
  - callback URL
- **Sandbox vs Production endpoint:** **Not implemented**.
- **Minimal connectivity test:** currently **not possible live**; only stub endpoint.
- **Order fetch test:** only stub data.
- **Webhook receive/verify:** not present.
- **Readiness:** Not ready.

---

## 3) What Mcray Must Provide Tonight (for live preflight)

### Shopify
- Shopify shop URL/domain
- Admin API token (or app key/secret + redirect/authorization code path)
- Scopes: `read_orders`, `read_products`, `read_inventory`, `write_inventory`, `write_webhooks`
- Shopify webhook secret and callback URL
- Topics to subscribe: orders/create, orders/updated, orders/paid, inventory_levels/update
- API version target

### TikTok Shop
- App Key / App Secret
- Redirect URI and callback URL
- Shop/Merchant ID
- Token acquisition and refresh credentials/procedure
- Webhook callback URL + signing secret
- Event topic subscription plan for order events

### Lazada
- App Key / App Secret
- Region / market selection
- Seller ID
- Access token flow + refresh method
- Webhook callback URL + signing secret
- Signature method/key for request verification
- Order-related endpoint scope/permissions

---

## 4) Debrief (Platform -> Readiness -> Blockers -> Next Action -> Confidence)

- **Shopify -> Readiness: NOT READY -> Blockers: no auth client, no API base URL config, no webhook endpoint/verification, no live fetch/push path, no rate-limit/idempotency/retry -> Next Action: build Shopify adapter + env/config + webhook route + mapping + scheduler -> Confidence: 12%**
- **TikTok Shop -> Readiness: NOT READY -> Blockers: no auth client, no endpoint routing, no webhook endpoint/verification, no order/push implementation -> Next Action: build TikTok adapter + token lifecycle + webhook handler with signature check + order ingest + retry -> Confidence: 10%**
- **Lazada -> Readiness: NOT READY -> Blockers: no auth/signature logic, no environment endpoint switch, no webhook endpoint/verify, no live order fetch/push -> Next Action: build Lazada adapter + sign/verify middleware + webhook endpoint + mapping/ reconciliation -> Confidence: 10%**

---

## 5) Non-Destructive Local Test Harness / Stub Commands

Added script:
- `./integration_preflight_harness.sh`

Run order:
1. Start app locally:
   - `cd ~/Desktop/nexray-main`
   - `python3 -m uvicorn server:app --reload --port 8000`
2. In another terminal run:
   - `BASE_URL=http://127.0.0.1:8000 ./integration_preflight_harness.sh`

Harness assertions:
- login succeeds for `admin / nexray2024_admin`
- channel create returns `id`
- each channel returns `sync_orders` with `success=true` and `stub=true`
- each channel returns `push_inventory` with `success=true` and `stub=true`

This is intentionally safe/no live traffic; it validates route wiring and DB-level integration plumbing only.

---

## 6) If Live Credentials Are Missing (Mock/Simulated Test Path)

- Keep the above harness as a **mock baseline** and treat any missing live checks as expected failures.
- Pass criteria for mock mode:
  - HTTP 200 + JSON schema valid on auth, channel create/list, stub sync, stub push.
  - `STUB-*` IDs may appear and must be deterministic enough for assertions.
  - No unhandled exceptions in 3rd-party route stack.
  - No data corruption in existing core tables (`channel_order_mappings` may grow with stub IDs).
- Live gating criteria (must be met tomorrow):
  - real orders returned and persisted with platform order IDs
  - webhook endpoints return 200 for valid signatures and 401/403 on tampered signatures
  - idempotency + retry behavior visible in DB and UI (`integration_events`/mapping records)
