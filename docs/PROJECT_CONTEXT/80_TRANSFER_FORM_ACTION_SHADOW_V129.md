# V129 — root-cause fix: hidden input named action shadows HTMLFormElement.action

## Production proof on 2026-10-28
After V128 installed successfully on gozaresh.filmjadiid.ir, the user still received `HTTP 404` for KHORSHID -> HOME stock transfer. They provided live `docker compose logs` identifying the precise failed request at 20:54:10 and again 20:54:49 (+0330):
```
POST /inventory/operations/[object%20HTMLInputElement] HTTP/1.1" 404
```
The actual legitimate paths `/inventory/operations/` and `/inventory/operations/transfer-direction/` both returned **403 application/json** for unauthenticated no-CSRF test POST via both the public IP and localhost Caddy. Django `reverse` and `resolve` agreed with both paths. Therefore the earlier attempts changing URL routes were NOT the root cause; Caddy, session auth and URLconf are not implicated by these observations. Form input `<input type="hidden" name="action" value="transfer">` creates a named-property collision with `HTMLFormElement.action`. The browser `transferForm.action` resolves to the HTMLInputElement itself; fetch stringifies it to `[object HTMLInputElement]` and resolves that as a relative URL. Django returns 404 before any transfer handler is reached. This explains why no stock moved.

## Surgical fix
V129 based exactly on successful V128 branch commit `05f7a4a0be0e4ed55b2997293cb2ab60b246c080`, with no DB schema, stock quantities, accounting, transfer backend, Caddy or HTTP routes altered:
- `templates/core/inventory_operations.html`: `fetch(transferForm.action,{...` becomes `fetch(transferForm.getAttribute('action'),{...`. Unlike the shadowed JS property, this reads the literal form attribute `/inventory/operations/`. The hidden `action=transfer` field remains, preserving the backend dispatcher. This is the only runtime application modification.
- `core/test_transfer_form_action_v129.py`: verify form and JS markers; Node test **executes the actual JS fetch target expression** with a simulated `transferForm.action` equal to an HTMLInputElement object, expects canonical path.
- `core/management/commands/check_transfer_form_action_v129.py`: read-only production static guard with no DB writes.
- `.github/workflows/check-transfer-form-v129.yml`: gated syntax and model checks, production Docker image build, disposable PostgreSQL transport/rollback/payment suites V126/127/128/129, shadowing test under Node, historical V123/V125 checks.
- `server_transfer_form_v129.sh`: adapted guard from V128: exactly pinned V128 baseline, allowlisted modifications, exact HTML blob hash, unchanged protected financial, stock, payment and warehouse backend sources and Caddyfile, SQL backup, finance and stock hashes PRE=PROJECTED=FINAL, PyPI-resilient Docker build and web-only recreate, read-only V129 audit both pre- and post-recreate. Deploy ONLY when current HEAD's CI is green. Success marker `SUCCESS: V129 TRANSFER FORM ACTION FIX DEPLOYED`. Never blindly retry transfers after network errors.

## Expected user verification
After safe deployment, hard refresh page, submit one genuine tiny color transfer, verify success JSON and that the corresponding transfer history, source KHORSHID decrease and destination HOME increase match. No browser dev tools required. If error appears, inspect `docker compose logs --since=3m web` actual POST path before further changes. Precise production evidence already grounds this fix; do not reopen generic Caddy or route debugging without new contrary evidence.
