# UI / INTEGRATION SAFETY V65 — DIGIKALA ZERO GUARD SAFE MODE

V65 must remain incapable of changing a Digikala listing.

Allowed:

- read Darma HOME + KHORSHID combined stock;
- persist zero/positive notification state in AppSetting;
- send Telegram notification on a new positive->zero transition;
- GET Digikala variants only;
- map title -> Darma ProductCode using the existing title-only resolver;
- map size using the existing size aliases;
- show a read-only list of potentially affected DKPCs;
- display a visibly locked deactivation action.

Forbidden in V65:

- PUT/PATCH business requests to Digikala;
- activation/deactivation endpoint calls;
- seller-stock mutation;
- automatic or manual Digikala listing changes;
- seller-code product identity;
- any sale/accounting/inventory/material/payment/return mutation;
- any HOME/KHORSHID transfer caused by this guard.

The bot may read the existing runtime token files. The RSA private key must remain outside the bot container.

Deployment must prove:

- `core/digikala_client_v40.py` is unchanged;
- no V65 source contains activation/seller-stock mutation endpoints;
- current accounting/inventory invariants are unchanged;
- V59/V60/V62/V63/V64 regressions still pass;
- V65 rollback regression passes;
- live mapping check prints `DIGIKALA WRITE CALLS = 0`.

Only a later explicitly authorized version may add real Digikala write behavior.


Network-failure rule:

- transient timeout/connection failure on GET mapping may defer mapping without failing SAFE MODE deployment;
- deferred mapping must print that Digikala writes are zero/absent;
- Telegram preview may retry later;
- network failure must never be converted into guessed mapping or a write.


Rate-limit rule:

- public API health may be read before variant mapping;
- when health reports current >= max, do not call /variants;
- a direct HTTP 429 from /variants must stop the scan immediately with no retry;
- 429 must never be treated as permission to guess from stale/unresolved rows;
- write mode remains absent/locked.


Health endpoint rule:

- the read-only health check must call exactly `GET /open-api/v1/` with the trailing slash;
- HTML seller-panel responses are not valid Open API health responses and must not be interpreted as rate-limit data;
- this health-path correction does not authorize any Digikala write.


Variant quota rule:

- public health rate_limit is informational only and must not be assumed to be the /variants quota;
- the first successful /variants page may expose data.meta_data.rate_limit, which is authoritative for continuing that mapping scan;
- if the first /variants call is 429, stop immediately with zero retry;
- if endpoint remaining quota is less than pages still required, stop before requesting the next page;
- partial variant mappings must never be presented as complete or used for a future write decision.
