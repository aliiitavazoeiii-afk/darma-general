> **CURRENT HANDOFF (2026-10-26):** The original AI_START_HERE text below stops at V37/V108-era assumptions and is HISTORICAL. **Read `docs/00_NEW_CHAT_READ_FIRST_V126.md` first.** Latest verified functional source is `v126-payment-history-filters` (SHA `90a79e993adced1689c70d5b0777ce2ea7f2789f`); full history in `docs/PROJECT_CONTEXT/75_MASTER_HISTORY_AND_FINAL_DECISIONS_V126.md`. This Git branch `docs-v126-complete-handoff-1405-08` is documentation-only and not a deploy target.

---

# AI START HERE — DARMA GENERAL

**CURRENT AUTHORITATIVE ENTRYPOINT: `docs/00_NEW_CHAT_READ_FIRST.md`**

Last current-context synchronization: **2026-08-29 after confirmed V37 production deployment**.

Repository: `aliiitavazoeiii-afk/darma-general`
Production domain: `gozaresh.filmjadiid.ir`
Production path: `/opt/darma-general`

## Required action for any new AI/chat

Do **not** begin work from the old v19-era handoff assumptions that used to live in this file.

Read, in order:

1. `docs/00_NEW_CHAT_READ_FIRST.md` completely.
2. Every numbered file in `docs/PROJECT_CONTEXT/` in the exact order specified there.
3. `UI_SAFETY_V37.md`.
4. Current `core/urls.py`.
5. The exact active source files for the requested subsystem.
6. `PROJECT_HANDOFF.md` only afterward for older forensic history.

The full previous contents of this file were preserved, not deleted, at:

`docs/archive/AI_START_HERE_v19_snapshot_20260827.md`

## Authority order

If documentation conflicts:

1. explicit current user business rule;
2. current active code + current physical/ledger evidence;
3. `docs/PROJECT_CONTEXT/*`;
4. `UI_SAFETY_V37.md`;
5. older `PROJECT_HANDOFF.md` / archived v19 handoff.

Never infer active behavior from a versioned filename alone. Always verify `core/urls.py` and imports.

## Hard safety rule

Accounting formulas, inventory valuation, sale economics, Digikala fee/receivable behavior, payment semantics, material consumption/output semantics, SaleSnapshot history and existing ledgers are frozen unless the user explicitly asks to change a business rule.

UI-only changes must not alter persistent business values.

## Latest confirmed live checkpoint at this handoff

Successful production marker:

`SUCCESS: STANDALONE RETURNS + CALCULATOR V37 DEPLOYED`

Last confirmed invariant snapshot:

```text
CAPITAL=5441972371
FINISHED=1115731500
RAW=1994448050
DIGI=812517154
DARMA=12072
TAKVIN=1195
NOVANI=3630
SALES=202
ACCOUNT_ENTRIES=206
```

These are historical/live checkpoint values as of that deployment, not permanent reset targets.

For full detail, read the context pack rather than relying on this gateway file.
