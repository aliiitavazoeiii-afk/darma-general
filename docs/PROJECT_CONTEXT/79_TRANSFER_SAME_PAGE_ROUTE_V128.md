# V128 — Canonical same-page AJAX transfer route: /inventory/operations/

## Parent, symptom, constraints
Base V127 revision: `32a9b545c2ba1a7b707e5d64c6acbc7614672ffe`. The operator reported that after V127's JSON response guard, transfer KHORSHID -> HOME returned **HTTP 404** (HTML), and confirmed **no transfer was registered**. V127's dedicated action `/inventory/operations/transfer-direction/` exists in `core/urls.py` and isolated tests, but that does not prove what the production proxy receives or why it issued a 404. Source of the 404 is not yet proven (could be proxy, deployment route mismatch or another server layer). No direct access to private production HTTP logs. Do not assert a specific Caddy cause.

## V128 corrective routing
The operations page already serves GET `/inventory/operations/` in production. V128 removes the separate-path requirement for the transfer form:
- `templates/core/inventory_operations.html`: transfer form action uses the canonical `{% url 'inventory_operations' %}` exactly like the page URL; AJAX still submits `action=transfer` and `FormData`, retains selectors, refreshes stock chips, clears only posted qty fields and never resubmits automatically after a transport error.
- `core/inventory_operations_v16.py`: intercept ONLY authenticated AJAX POSTs with `action=transfer`, dispatch into `inventory_transfer_v123.inventory_transfer_direction` and return its JSON result unmodified. All other operations (GET and manual stock adjustment POST) retain existing original V16 code and behavior. An outer V127-compatible `transfer_ajax_auth` wrapper emits 401 JSON for anonymous AJAX rather than an HTML login redirect.
- `core/inventory_transfer_v123.py`: the same narrow CSRF failure response now covers AJAX POST at BOTH canonical and legacy transfer routes. No bypass. Existing `/inventory/operations/transfer-direction/` remains registered for compatibility.
- This does not change stock direction mapping, quantities, validation, row locks, transfer movement service, database schema, existing history, dashboard or financial logic. It preserves V127's transaction covering transfer, snapshot and JSON response serialization.

## Checks and release
- `core/test_transfer_same_page_v128.py`: inherits full isolated V127 transport and ledger test suite, targeting the SAME operations POST used for GET; verifies successful real stock movement, shortage rejection, snapshot failure rollback, JSON 401/403, normal login redirect, HTML form action path, and V123 legacy endpoint compatibility.
- `core/management/commands/check_transfer_same_page_v128.py`: read-only route/CSRF/auth check, no stock or money mutation, safe on prod.
- `.github/workflows/check-transfer-route-v128.yml`: syntax, migrations check/dry-run, Docker build/privacy check, isolated PostgreSQL DB tests for V126/V127/V128 and read-only V123/V125 regressions.
- `server_transfer_route_v128.sh`: guarded script from V127; compares exact V127 parent, only approved diff files, exact V16/V123/template blob hashes, pre-deploy PostgreSQL dump, Caddyfile hash retained, Docker PyPI timeout/retries, V121 finance repair preview only, all read-only regressions, protected 20 model row hashes PRE=PROJECTED=FINAL and **web-only** container recreate; no migrations or ledger fixes.
- `git pull --ff-only origin v128-transfer-same-page-route && bash server_transfer_route_v128.sh` from `/opt/darma-general` only after latest CI HEAD is green; success marker `SUCCESS: V128 CANONICAL TRANSFER ROUTE DEPLOYED` and `PRE = PROJECTED = FINAL`. Do not claim deployment without that marker.
- Live functionality requires one operator-authorized small transfer after confirming production deployment, checking both physical balances and the transfer history.
- If a 404 persists even for same-page POST, inspect sanitized actual Caddyfile and POST response URL/status without guessing; do not retry blindly.
