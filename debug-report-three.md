# NEXRAY Debug Room — Agent 3 (PASS B + PASS C)
**Scope:** Backend/runtime/config + integration fault review and second frontend validation pass.
**Repo:** `~/Desktop/nexray-main`
**Date:** 2026-03-06

## Executive Summary
Two-pass review found **multi-tenant authorization bypass, hardcoded credentials logic, and SPA/runtime boundary hazards** that can surface as visible frontend glitches (blank UI, wrong-tenant data leaks, or impossible login behavior under deploy variation). No test suite is present in repo.

---

## PASS B — Backend / Runtime / Config / Integration

### Priority Queue (B-side, highest first)

1. **Critical — Credential model is effectively username-derived / non-configurable**
   - **Why it matters:** Auth can be predicted and reused; create-user flow still uses username hash instead of password hash.
   - **Evidence:**
     - Login compares only `sha256('nexray2024_' + username)` in `/api/auth/login` (not incoming password): `server.py:835`.
     - Demo seeding computes the same hash from username only: `server.py:669`.
     - User creation has conditional branch but still hashes by username even when body password is supplied: `server.py:1481-1484`.
   - **Frontend-visible impact:** Any security incident can immediately become tenant-wide operational integrity issue; also creates misleading UI assumptions if password UX suggests custom passwords.
   - **Immediate queue action:** Replace all auth hashing with Argon2/bcrypt over submitted password + per-user salt; migrate `password_hash` schema if needed.

2. **Critical — Catch-all static route allows path traversal and arbitrary file read via `/static` parent escape**
   - **Why it matters:** `/{path:path}` concatenates user input directly into file path.
   - **Evidence:** `server.py:2434-2441` sets `file_path = f"static/{path}"` and serves when `os.path.isfile(file_path)`.
   - **Integration risk:** If reverse proxy/frontend error requests or crafted URL hit server, attacker can read files within parent directory tree that should not be served.
   - **Immediate queue action:** Canonicalize and sandbox-check path before read (`resolve()`, prefix check to static root); or replace with safe static serving.

3. **High — Multi-tenant isolation bypass by user-controlled `entity_id` in endpoints**
   - **Why it matters:** Most endpoints take `entity_id` from query params, default to one value, and do not assert against `request.user.entity_id`.
   - **Evidence (examples):**
     - Dashboard: `get_dashboard(request, entity_id=...)` only filters by passed ID: `server.py:900-907`.
     - Warehouses: same pattern: `server.py:999-1010`.
     - Suppliers/Customers/Items/Movements etc. follow same pattern from their route signatures (`@app.get("/api/...", entity_id=...)`).
     - Write endpoints also accept body entity IDs without matching session entity (e.g., `/api/warehouses` create: `server.py:1289-1299`, `/api/supplier_orders`: `server.py:1525+`, create location/item/customer/user etc.).
   - **Frontend-visible impact:** If a user tampers with localStorage or intercepted calls, backend will return/modify wrong tenant data; UI can appear as “stale/wrong data” instead of explicit auth errors.
   - **Immediate queue action:** Derive `entity_id = user['entity_id']` (or RBAC override matrix) in backend and ignore or validate client-supplied entity ids.

4. **High — Catch-all serves HTML for unknown `/api/*` paths (API 404 is hidden)**
   - **Why it matters:** API mistype/unregistered routes become HTML, so frontend JSON parsing falls back to generic `null` and sections silently fail.
   - **Evidence:**
     - `server.py:2434-2443` returns `static/index.html` for non-file path.
     - API client assumes JSON and returns `null` on all fetch issues: `static/app.js:52-61`.
   - **Immediate queue action:** In `/{path:path}`, short-circuit `if path.startswith('api/')` to return JSON 404, not HTML.

5. **Medium — No cache policy for frontend artifacts / immutable deployment behavior**
   - **Why it matters:** No explicit `Cache-Control` headers for `/api/*` or SPA shell/JS/CSS endpoints; old bundles can stick around in shared/proxied deployments.
   - **Evidence:** no cache-control headers set near static serving block in `server.py:2424-2443` and API responses are plain JSON defaults.
   - **Immediate queue action:**
     - Add `Cache-Control: no-store` for HTML/API responses;
     - immutable+hash cache headers for static assets (or add filename hash versioning) and ensure deployment invalidates old artifacts.

6. **Medium — CORS is absent; frontend coupling assumes same-origin only**
   - **Why it matters:** Any deployment separating UI and API domain breaks with browser CORS errors (frontend appears empty/fails at runtime).
   - **Evidence:** imports only `FastAPI`/`StaticFiles` and no `CORSMiddleware`; see top-level imports and app setup (`server.py:7-23`).
   - **Immediate queue action:** Add CORS middleware with explicit allowlist tied to environment profile.

7. **Medium — Missing validation around DB deployment state**
   - **Why it matters:** `init_db()` runs `CREATE TABLE` + seed only and does not handle schema drift; any deployment with schema mismatch can silently fail partially. `NEXRAY_DB_PATH` defaults to relative path `nexray.db`.
   - **Evidence:** `init_db` / schema creation and seed-only logic: `server.py:94-104`, `server.py:642-647`, `server.py:20`.
   - **Immediate queue action:** Add migration guard + startup validation; require explicit DB path + volume mount in production.

---

## PASS C — Frontend-focused validation (independent pass)

### Priority Queue (C-side)

1. **High — Hardcoded tenant/warehouse IDs create deployment fragility**
   - **Evidence:**
     - Frontend defaults to `ent-01` globally: `static/app.js:4`.
     - Warehouse selectors hardcode `wh-01|wh-02|wh-03` in modal templates: `static/app.js:658`, `static/app.js:980`.
     - Frontend bootstrap call fetches `locations` from hardcoded warehouse (`wh-01`) in `loadInventory`: `static/app.js:1058`.
   - **Impact:** With different seeded data, renamed/removed IDs, or non-default tenant state, user sees empty dropdowns and dead inventory screens.
   - **Action:** Use IDs loaded from `/api/warehouses` and `/api/locations` by selection, not hardcoded constants.

2. **High — Potential deep-link asset failure from relative asset loading + SPA fallback**
   - **Evidence:** (from app shell) assets are loaded via relative path in index; combined with catch-all fallback route this can break on non-root URLs.
   - **Impact:** Direct URLs (or stale links) can produce blank/partially loaded pages.
   - **Action:** Use root-relative asset URLs (`/base.css`, `/style.css`, `/app.js`) and keep `index` canonical.

3. **Medium — API helper swallows failures as silent `null`**
   - **Evidence:** Every request wrapper catches all errors and returns `null` without surfacing a user-level detail: `static/app.js:49-61`, `64-76`, etc.
   - **Impact:** UI sections fail silently and leave ambiguous loading states; troubleshooting takes longer and false-negatives can hide integration regressions.
   - **Action:** Add standardized API error envelope + toast + visible status banner; reject hard when response is non-JSON/non-2xx.

4. **Medium — Global `event` dependency in action handlers**
   - **Evidence:** `runReconciliation` and duplicate action handler use `const btn = event.target;` directly: `static/app.js:443`, `static/app.js:1878`.
   - **Impact:** Calling handlers from keyboard shortcuts, future refactors, or automated tests can fail with `event is not defined`.
   - **Action:** Pass event explicitly (`onclick="runReconciliation(event)"`) and guard null.

5. **Medium — Endpoint contract drift risk between frontend and backend defaults**
   - **Evidence:** `api()` forces `entity_id` on all GET calls (`api` wrapper): `static/app.js:49-50`; backend expects entity in many endpoints but several paths also default to fixed values (`/api/locations` defaults `wh-01`, `server.py:1014-1016`).
   - **Impact:** Data filters become invisible/implicit; behavior differs if defaults change in one side.
   - **Action:** Make defaults explicit per-page; avoid adding unknown params globally.

---

## Missing / High-risk tests

No automated tests found in repo (no `tests/`, no `pytest`/`playwright` config).

### Recommended test additions (priority)
1. **Auth hardening tests (backend)**
   - Login with wrong password must fail.
   - Password change/creation should validate stored bcrypt/argon hash.
2. **Tenant isolation tests (backend)**
   - Attempt cross-entity read/write for each sensitive endpoint using low-privilege token.
3. **Static route security tests (backend)**
   - path traversal (`/../server.py`) should be blocked.
4. **API contract tests (backend/frontend)**
   - Validate 404 JSON shape for missing `/api/*` endpoints and front-end handles it visibly.
5. **Frontend smoke test matrix (E2E)**
   - Navigate every nav route + deep links; assert JS bundle and CSS load and pages render metrics.
6. **Cache/invalidation smoke test**
   - New deploy should invalidate old JS bundles and force fresh `app.js`/CSS load.

---

## Quick Hive Queue (Actionable)
1. **Patch auth hashing + create-user hash logic** (P0 security).
2. **Fix catch-all path handling (path traversal + API 404 behavior)** (P0).
3. **Lock tenant enforcement to session entity on all /api list/create/query endpoints** (P1).
4. **Replace frontend hardcoded entity/warehouse IDs with dynamic options from API** (P1).
5. **Set cache headers + deploy immutable static strategy** (P1).
6. **Add CORS + explicit deployment matrix; verify separate-domain frontend/API** (P2).
7. **Build minimal backend+frontend regression suite and run in CI** (P2).
