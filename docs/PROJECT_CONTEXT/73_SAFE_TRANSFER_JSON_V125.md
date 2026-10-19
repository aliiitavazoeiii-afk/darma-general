# V125 — Do not parse HTML as JSON or accidentally double-transfer physical inventory

Base branch: `v124-dashboard-chart-repair`. Owner's browser showed `Unexpected token '<', "<!doctype ..." is not valid JSON` immediately after submitting `از خانه به انبار`. This JS exception is **not evidence that the stock transfer was not saved**. The response may have been an HTML 404 due to old running Django image (previous V123 deployment had stopped before web recreation), CSRF 403, expired session redirected to HTML login, proxy HTML 50x, or other non-JSON response. No server logs available yet, so do not claim exact response code/cause.

## Minimal changed behavior

- Existing stock transfer route and Django StockTransfer/InventoryMovement ledger remain; do NOT change accounting or DB schema.
- `templates/core/inventory_operations.html`: before sending any POST, make a read-only GET probe to the existing endpoint, requiring JSON `{ok:true,version:"v125"}`. Stale image/login/404/HTML fails before stock writes. On submission, accept only JSON with correct V125 and HTTP status; non-JSON responses produce legible diagnostic including HTTP code, not raw parser error. Do not clear form on failed/unknown response. Keep date, brand, size and direction after confirmed success; still clear entered quantities only. Real browser refresh resets to default warehouse→home.
- Every submit carries one cryptographically random UUID `request_token` in a hidden field while the attempt is unresolved, generated in-memory only. No localStorage, no per-user persistence and no extra app state. Prevent user from re-submitting while a response is ambiguous and current transfer presence cannot be confirmed.
- Django `transfer()` validates UUID and stores `web-transfer:v125:<UUID>` in the existing unrestricted `StockTransfer.note`, without adding a column. It acquires a row lock on the Darma brand so identical concurrent UUID submissions serialize; previously successfully committed UUID returns original transfer IDs after verifying exact date, brand, size, direction, color/qty and applied status. This makes repeats **exactly-once with respect to that request token**, avoiding double stock consumption.
- The same endpoint GET can confirm whether that request UUID already produced applied transfer rows; if yes, browser recovers after an HTML/proxy error, updates chips and reports confirmed success without re-posting. If status probe cannot be obtained, user is warned to inspect history manually; no automatic retry.
- AJAX expired-session request returns JSON 401 rather than HTML login redirect; regular browser non-AJAX login redirects remain.
- Even if stock snapshot generation fails after committed transfer, POST returns JSON 200 success with `refresh_needed:true`, rather than a false failure indication. GET status is also JSON if snapshot can't be computed.
- Existing CSRF middleware may still generate its own HTML 403 before the view; the client checks response type and reports a readable error. Never weaken CSRF protection.

## Safeguards and diagnostics
- No automatic migration, stock transfer, ledger mutation, user balance mutation, sidebar/chart/material change by installer.
- Prior failed V123 migration 0021 already applied successfully. An old V123 web container could have served old routes because preflight hash mismatch prevented recreate; the new GET probe identifies old container before transferring.
- Isolated Django/PostgreSQL tests: successful transfer and repeated same UUID leave exactly two inventory movement rows, mismatched replay refused, unauthenticated AJAX JSON 401, source shortage JSON 400, probe GET read-only, snapshot failure after commit still success JSON.
- Branch `v125-safe-transfer-json`; guarded deploy `server_safe_transfer_json_v125.sh` ensures local Caddyfile and existing ERP business data hash PRE=PROJECTED=FINAL. Live site only updates after web container recreation and smoke check.
