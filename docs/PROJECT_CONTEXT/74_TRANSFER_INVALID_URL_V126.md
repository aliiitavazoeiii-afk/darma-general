# V126 — Fix "Failed to construct 'URL': Invalid URL" in inventory transfers

Parent: V125 `v125-safe-transfer-json`.

## Confirmed root cause

The existing `templates/core/inventory_operations.html` inline script declares `const location=document.getElementById('adjust-location')` to refer to the **inventory adjustment location SELECT**. Inside the same lexical scope, V125 `probe()` inadvertently used `new URL(transferForm.action,location.href)`, expecting the built-in browser location. This is a local name collision: the select has no `.href`. In browsers where `transferForm.action` is not an already fully qualified URL, construction fails with `Invalid URL` **before GET or POST**. The user reported `Failed to construct 'URL': Invalid URL هیچ درخواست ثبت انتقال ارسال نشد.` This particular attempt did NOT invoke the transfer POST (the former request might still have committed; inspect recent history separately if needed).

## Scope of fix

The only production UI change is `templates/core/inventory_operations.html`:

- Declare `const transferEndpoint="{% url 'inventory_transfer_direction_v123' %}";`, resolved server-side by Django to the same-origin relative transfer endpoint.
- Read-only GET preflight: `fetch(transferEndpoint+(token ? '?request_token='+encodeURIComponent(token) : ''),...)`.
- POST: `fetch(transferEndpoint,...)`.
- Eliminate use of `new URL()` and `location.href` in this transfer handler. The separate local select still functions for inventory adjustment; **no broad refactor**.
- Keep V125 checks: preflight JSON/version, auth and CSRF-readable errors, never retry an ambiguous transfer without read-only UUID lookup, exact-once anti-duplicate transaction marker, date/brand/size/direction persistence until user manually reloads.
- NO changes to Django URL routing, models, stock movement calculations, financial entries, database schema, Caddyfile or unrelated pages.

## Tests

`scripts/test_transfer_url_v126.js` executes the actual embedded JS source in a Node VM with a mocked adjustment dropdown named `location` that intentionally has **no href**. Assertions: GET request hits `/inventory/operations/transfer-direction/` before POST, no new URL constructor, form does not reload, success clears only quantity, and no browser history/base URI required. GitHub Action `check-transfer-url-v126.yml` runs it and repeats all V125 Django/Postgres exact-once transfer tests on a disposable test DB.

## Deployment

Branch `v126-transfer-url-fix`, guarded script `server_transfer_url_v126.sh`, based on V125 with updated SHA parent and limited file allowlist. SQL backup, protected ERP data hashes PRE=PROJECTED=FINAL and local Caddyfile preservation; no migrations. URL preflight checks refuse to deploy if old constructor remains. After success, reload inventory operations page with **Ctrl+F5** (inline script).
