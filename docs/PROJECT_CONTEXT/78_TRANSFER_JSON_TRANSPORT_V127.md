# V127 — Durable AJAX stock-transfer JSON protocol and atomic response

**Functional parent:** V126 `v126-payment-history-filters` at `90a79e993adced1689c70d5b0777ce2ea7f2789f`.
**New branch:** `v127-transfer-json-atomic-response`.
**Scope:** `/inventory/operations/transfer-direction/`, associated inventory operations template, and narrowly scoped CSRF response configuration.

## Reported production symptom
Operator saw `Unexpected token '<', "<!doctype"... is not valid JSON` when submitting KHORSHID -> HOME manual transfer. This unequivocally means the browser attempted JSON parsing on an HTML response; it does NOT by itself identify which HTML document or guarantee that no stock movement committed. Production HTTP response status, redirect target, and logs were not available at authoring time. Plausible causes include authentication redirection, Django CSRF 403, or an HTML error emitted by a proxy or app. Do not claim to have verified the specific source until inspecting sanitized runtime evidence.

## Code-level root cause
The V123 transfer browser client unconditionally ran `await response.json()`. It did not inspect content type or redirected login responses. `@login_required` returned a 302 login redirect with HTML after fetch followed the redirect; CSRF middleware produced HTML 403 before the view; proxy failures can return HTML 5xx. These paths surfaced only as cryptic parser errors.

There was a second genuine transactional risk: `transfer()` completed in its own `transaction.atomic`, then the handler built a fresh stock snapshot outside the transaction. If snapshot generation failed, the handler returned an error though the transfer had ALREADY committed, inviting duplicate submission.

## V127 final behavior
- `_ajax()` and `transfer_ajax_auth` return a typed JSON 401 for AJAX requests with expired or absent login, retaining regular redirect behavior for ordinary browser requests.
- `CSRF_FAILURE_VIEW` is set to `core.inventory_transfer_v123.csrf_failure`. Only the exact AJAX transfer path receives JSON 403 with a user-facing expired-CSRF message; every other path continues Django's default CSRF failure behavior. No CSRF protection is disabled.
- Browser submits using `Accept: application/json`, confirms the `Content-Type`, distinguishes HTML login/403/5xx from valid JSON, and reports actionable Persian messages. It never displays `Unexpected token` and never retries an ambiguous transfer automatically.
- A single outer `transaction.atomic` now covers `transfer()`, the updated stock snapshot, and the serialization of the success `JsonResponse`. Any exception aborts ALL affected `StockTransfer`, `InventoryMovement`, and `StockBalance` writes.
- Successful AJAX still retains selected date, brand, size and direction, clears only submitted quantity fields, updates stock chips and shows the same success. Real reload still defaults to warehouse->home.
- No sale auto-transfer, no changes to stock valuation/capital, raw materials, Novani or finance, no new models or migrations. Business validation and source-stock shortage checks remain.

## Tests and safeguards
- `core/test_transfer_transport_v127.py`: isolated Django database tests for anonymous JSON 401, CSRF JSON 403, ordinary login redirect, successful transfer balance/movement/combined-stock invariants, source insufficiency abort, and an injected failing stock snapshot that must roll back all physical writes.
- `core/management/commands/check_transfer_transport_v127.py`: read-only route/auth/CSRF/client-contract audit, safe on production. Does not post transfers or modify DB.
- `.github/workflows/check-transfer-transport-v127.yml`: isolated PostgreSQL, Django checks, syntax and regression tests including V126 filter and V123/V125 material rules.
- `server_transfer_json_v127.sh`: guarded web-only deployment based on V126, exact branch/parent allowlist, source blob pins, original Caddyfile preserved, pg_dump backup, existing V121 migration/repair preview guards, no new migrations, V123–V126 read-only regression checks, snapshot hashes PRE=PROJECTED=FINAL for stock, money, sale and wholesale tables. No historical repair/reset.
- Production smoke after install: submit ONE small authorized transfer from the UI and check historical transfer ledger and source/destination quantities; this is operator action, never performed during CI or installation.

## Status
GitHub branch development is distinct from deployed VPS. Do not describe V127 as live until its exact CI HEAD is green and the server prints `SUCCESS: V127 TRANSFER JSON + ATOMIC RESPONSE DEPLOYED` with `PRE = PROJECTED = FINAL`. If the user still sees a failure, capture the Network response status, final URL and content type plus sanitized Caddy/web logs before diagnosing. Never post the same transfer again solely because a transport error appeared.
