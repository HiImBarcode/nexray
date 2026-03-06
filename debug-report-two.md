# NEXRAY Debug Room — Agent 2 Audit A
## Scope
Deep code review for UI stability/layout across frontend+backend (sidebar/nav/render pipeline focus), with static/asset serving and runtime hydration checks.

## Checks run
- `node --check /Users/mcrayai/Desktop/nexray-main/static/app.js` ✅
- `python3 -m py_compile /Users/mcrayai/Desktop/nexray-main/server.py` ✅

---

### Finding 1 — High — Untrusted path traversal via SPA fallback route in backend
**Evidence**
- `server.py` has catch-all route:
  - `file_path = f"static/{path}"`
  - then `if os.path.isfile(file_path): return FileResponse(file_path, ...)`
  - with no path normalization / sandboxing.
- Route matches any URL path after API routes, including values like `../server.py` if URL-decoded.
- This can read files outside `static/` while still returning `200 + binary/text` responses (not blocked by a security root check).
- Relevant lines: `server.py:2430-2441` (shown at end of repo around static section).

**Fix**
- Resolve and validate path against a fixed static root before read:
  - `STATIC_DIR = Path(__file__).resolve().parent / "static"`
  - `candidate = (STATIC_DIR / path).resolve()`
  - if `candidate` does not startwith `STATIC_DIR` => `HTTPException(400, ...)`
- Keep `is_file()` check only after canonicalization.
- Prefer `safe_join` / `pathlib` and reject `..` traversal segments.

**Confidence**
- **High (0.98)** — deterministic security + stability issue, reproducible with traversal segments; high risk of serving unintended files.

---

### Finding 2 — Medium — Relative asset URLs can break on SPA deep-link URLs with trailing path segments
**Evidence**
- `index.html` loads core UI assets with relative URLs:
  - `./base.css`, `./style.css`, `./app.js`.
- SPA fallback renders `index.html` for non-file routes under catch-all, so pages like `/outbound/` (or app-mounted subpaths) can cause browser URL base to resolve these resources unexpectedly (`/outbound/app.js`), which then falls through SPA catch-all and returns HTML instead of JS/CSS.
- This yields silent JS/bootstrap failure (blank UI / runtime errors) depending on incoming URL normalization.
- Relevant lines: `static/index.html:10-11` and `static/index.html:273`; backend fallback route: `server.py:2430-2441`.

**Fix**
- Convert asset references to root-absolute URLs and optionally `defer` script:
  - `/base.css`
  - `/style.css`
  - `/app.js` (or better, templated `{{ static_root }}`)
- Optionally add `<base href="/">` if full relative links remain elsewhere.

**Confidence**
- **Medium-High (0.86)** — URL base resolution edge cases are common in SPA deployment; this is a known fragility that causes intermittent broken boot on deep links.

---

### Finding 3 — Medium — Catch-all route returns HTML for missing API paths, causing frontend JSON parse failure masking backend/API defects
**Evidence**
- Any unmatched path (including `/api/*` typos or removed endpoints) can reach the `/{path:path}` handler.
- For non-file API-like paths, code returns `static/index.html` instead of API-style JSON 404.
- Frontend `api()` expects JSON and catches parse exceptions as generic `null`, causing silent page sections to fail render without clear signal.
- Relevant lines: `server.py:2434-2441` and client JSON consumers (`api(...)` calls throughout `static/app.js`).

**Fix**
- In catch-all route, short-circuit API-like paths:
  - `if path.startswith("api/"):` return `JSONResponse({"detail":"Not Found"}, status_code=404)`.
- Keep SPA fallback only for non-API frontend routes.
- Optionally add explicit `404` handling and logging for unknown API routes.

**Confidence**
- **Medium (0.83)** — deterministic path behavior in FastAPI routing; impacts diagnostics + runtime stability when endpoint contracts mismatch.

---

### Summary / priority
1. **Path traversal risk** (Critical for backend security and stability) should be patched first.
2. **Relative SPA asset paths** should be normalized to absolute/static-safe paths to avoid deep-link hydration breakage.
3. **API 404 behavior** should return JSON for unmatched `/api/*` to avoid front-end null/blank failures.