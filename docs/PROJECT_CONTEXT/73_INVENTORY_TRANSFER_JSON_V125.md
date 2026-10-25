# V125 — AJAX inventory transfer receives HTML instead of JSON

Parent V124 `v124-dynamic-payment-fabric-colors` HEAD `1cc238e7570ed43c89ae47f6bafe596b0846fb4c`. New branch `v125-inventory-transfer-json-safety`.

## Symptom
User reports that transferring physical stock from خورشید to خانه at `/inventory/operations/` displays `Unexpected token '<', "<!doctype"... is not valid JSON`.

## Cause and narrow correction
The operations-page JS calls `response.json()` unconditionally after AJAX POST to `/inventory/operations/transfer-direction/`. The Django view was decorated with `@login_required`, which redirects expired logins to an HTML login page (HTTP 302 -> 200) rather than returning JSON. HTML may also be caused by CSRF 403 or reverse-proxy/upstream HTML 502. Without a live failing request HTTP status or server logs, the precise source of THIS user's HTML cannot be established; these cases are now handled explicitly.

- Keep the endpoint protected: unauthenticated AJAX POST responds HTTP **401 application/json**, `{"ok":false,"code":"login_required","message":"..."}`; old non-AJAX form submission still redirects to login. No database write happens for logged-out users.
- Frontend first checks `Content-Type`; distinguishes login redirect/401, CSRF 403, and unexpected HTML/server failure without calling `response.json()` on HTML. Safely handles malformed JSON and avoids making assertions about whether a transfer committed when server communication was lost.
- On success, keep current date/brand/size/direction selections and clear ONLY the submitted quantity boxes. On errors, preserve entries for review, and **never auto-retry**. If outcome uncertain, instruct user to inspect stock balances and latest transfer rows before manual retry. This prevents accidental double transfer.
- No changes to the stock-transfer transaction, StockBalance or InventoryMovement arithmetic, database migrations, material report, accounting, existing wholesale/finance, Caddyfile, or sidebar.

## Tests
`core/test_inventory_transfer_json_v125.py`: isolated Postgres test client tests unauthenticated 401 JSON, non-AJAX login redirect, authenticated warehouse->home and home->warehouse success with exactly two movement rows/unchanged combined stock, shortage 400 JSON and unchanged physical stock, CSRF 403 and no stock changes. CI also extracts the inline JS and runs `node --check`. `check_inventory_transfer_json_v125` checks unauth AJAX result and template guards read-only in production.

## Deployment
`bash server_inventory_transfer_json_v125.sh` requires V124 already running, builds using V124 safe trusted registry base-image fallback (Docker Hub CloudFront 403 workaround), captures PostgreSQL backup and previous protected ledger/physical-stock table hashes, verifies Caddyfile unchanged, checks the existing V124/V123 regression suite + V125, and recreates web only after tests pass. No migrations or automatic stock/finance writes.

Success: `SUCCESS: V125 INVENTORY TRANSFER JSON FIX DEPLOYED` with `PRE = PROJECTED = FINAL`.

## Confirmed root cause from 2026-10-25 live Gunicorn access logs

User supplied live logs: `POST /inventory/operations/[object%20HTMLInputElement] HTTP/1.1" 404` twice (10:06 and 11:18 +03:30), while GET `/inventory/operations/transfer-direction/` returned 405 and anonymous POST to that correct URL returned expected CSRF 403. This DISPROVES the initially suspected route absence or Caddy routing fault in those requests; requests used the *wrong URL*. The transfer HTML form has `<input type="hidden" name="action" value="transfer">` and frontend originally did `fetch(transferForm.action, ...)`. The form property `action` is shadowed by an `HTMLInputElement` named `action`, coerced to `[object HTMLInputElement]` in fetch, so Django correctly responds 404. Root cause of the reported user-specific 404 is confirmed.

**Hotfix on the same V125 branch**: `const endpoint=transferForm.getAttribute('action')` and `fetch(endpoint,...)`. Verify the literal path `/inventory/operations/transfer-direction/` before POST. Keep hidden `name=action` for request format compatibility; keep existing CSRF/401/HTML guards. Read-only `check_inventory_transfer_json_v125` now fails if JS uses `fetch(transferForm.action,...)`. CI checks full page JavaScript syntax, transfer logic on isolated PostgreSQL and this path regression. No transfer with the above logged bogus 404 URL could enter the valid transactional transfer handler, so those particular 404 requests did not mutate stock.
