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
