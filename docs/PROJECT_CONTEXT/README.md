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
16. `16_UI_MODERNIZATION_V38.md`
17. `17_LOGO_TYPOGRAPHY_V39.md`
18. `18_DIGIKALA_API_V40.md`
19. `19_DIGIKALA_DELIVERIES_V41.md`
20. `20_DIGIKALA_FREE_WAREHOUSE_V42.md`
21. `21_DIGIKALA_CENTER_V43.md`
22. `22_DIGIKALA_CENTER_V44.md` — fixes future-date commitment split, inventory-backed old/current products, sales endpoint fallback, physical return-warehouse detection, and multi-worker/shared API caching.
23. `23_DIA_GALLERY_V45.md` — separate daily sales channel consuming Darma color/size stock at fixed 71,000 toman per short, with its own receivable included in accounts/capital.
24. `24_NO_AUTO_TRANSFER_V46.md` — explicit new rule: every Darma-backed sale deducts HOME only and may make HOME negative; KHORSHID changes only through explicit manual transfer; post-day-3 phantom auto-transfers are reversed without changing combined stock/capital.
25. `25_BLACK_RED_UI_V47.md` — reversible presentation-only black/charcoal/red runtime theme, dark Darma logo plaque, aligned comprehensive-report KPI grid, DB/UI backup, and one-command rollback.

Important supersession rule for V46: older statements in `01`/`05` that sale logic may auto-transfer KHORSHID -> HOME are obsolete. `24_NO_AUTO_TRANSFER_V46.md` is authoritative for sale location behavior.

After these, read `UI_SAFETY_V37.md` through `UI_SAFETY_V47.md`, then current `core/urls.py`, exact active source files, and older handoff docs last.

When older docs conflict with this directory or current active code, the later explicit business-rule document + current active code wins.

The last numerically recorded production checkpoint remains V38 until a newer deployment's actual final invariant block is posted by the user. V46/V47 must not be called fully production-confirmed without their successful server output markers. V47 is a runtime visual overlay and does not alter tracked business/template/CSS source.

Latest confirmed numeric production snapshot:

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

Standing rule: after every important change update context; after every confirmed successful deployment update the live checkpoint with actual server output.
