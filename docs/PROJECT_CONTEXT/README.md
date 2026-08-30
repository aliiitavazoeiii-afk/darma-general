# PROJECT_CONTEXT MANIFEST

This directory is the authoritative, detailed continuation pack for a new AI/chat.

Read `../00_NEW_CHAT_READ_FIRST.md` first.

Then read all numbered files in order:

1. `01_BUSINESS_RULES_AND_INVARIANTS.md`
2. `02_ACCOUNTING_FORMULAS_AND_LEDGER_SEMANTICS.md`
3. `03_ACTIVE_CODE_MAP.md`
4. `04_SALES_DIGIKALA_AND_RETURNS.md`
5. `05_INVENTORY_MATERIALS_PRODUCTION_PAYMENTS.md`
6. `06_DEPLOYMENT_SAFETY_AND_RECOVERY.md`
7. `07_BUG_HISTORY_AND_DO_NOT_REPEAT.md`
8. `08_LIVE_STATE_AND_CHECKPOINTS.md`
9. `09_UI_AND_USER_WORKFLOW_CONTRACT.md`
10. `10_EXACT_BASELINES_CATALOG_AND_SPECIAL_CASES.md`
11. `11_DATA_MODEL_AND_LEDGER_RELATIONSHIPS.md`
12. `12_VERSION_TIMELINE_V18_TO_V37.md`
13. `13_NEW_CHAT_OPERATING_PROTOCOL.md`
14. `14_HANDOFF_SCOPE_AND_COMPLETENESS.md`
15. `15_CODE_FINGERPRINT_AT_HANDOFF.md`
16. `16_UI_MODERNIZATION_V38.md` — post-handoff V38 UI-only timeline/fingerprint delta, confirmed live.
17. `17_LOGO_TYPOGRAPHY_V39.md` — Darma logo + cleaner Persian typography; committed on GitHub, not separately confirmed live.
18. `18_DIGIKALA_API_V40.md` — direct Digikala Open API read-only dashboard integration, automatic token refresh and token/private-key isolation; committed on GitHub, not confirmed live until successful V40 server output.

After these, read:

- `/UI_SAFETY_V37.md`
- `/UI_SAFETY_V38.md`
- `/UI_SAFETY_V39.md`
- `/UI_SAFETY_V40.md`
- current `/core/urls.py`
- exact active source files relevant to the requested change
- `/AI_START_HERE.md` and `/PROJECT_HANDOFF.md` only for older historical context.

When older docs conflict with this directory or current active code, this directory + current active code wins.

For production status, `08_LIVE_STATE_AND_CHECKPOINTS.md` is authoritative only for deployments explicitly confirmed by server output.

Latest confirmed live deployment at this synchronization point: **V38 UI modernization**. V39 and V40 code are on GitHub but V40 is not production-confirmed until `SUCCESS: DIGIKALA READ-ONLY V40 DEPLOYED` is posted from the VPS.

Latest confirmed production snapshot:

```text
CAPITAL=5430972371
FINISHED=1115731500
RAW=1994448050
DIGI=812517154
DARMA=12072
TAKVIN=1195
NOVANI=3630
SALES=202
ACCOUNT_ENTRIES=206
```

Standing continuation rule from the user: after every important change, update the relevant context-pack files; after every confirmed successful deployment, also update the live checkpoint using the actual server output.
