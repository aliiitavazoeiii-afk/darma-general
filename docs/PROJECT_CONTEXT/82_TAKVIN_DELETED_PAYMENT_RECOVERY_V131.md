# V131 — recover one real deleted Takvin payment, only once, after confirming source bank

## Evidence
Read-only production `check_takvin_signed_v130` returned:
- current Takvin debt +50,000,000 toman (incorrect), last setting update 2026-10-29 10:22:15.031509 +03:30
- existing 3 BusinessPayments: ids 47:55,880,000; 43:10,000,000; 11:32,625,000; total 98,505,000
- 16 TakvinPurchase rows total 113,400,000
- current Mellat bank ExcelManualRow id=3 balance 168,807,018; Mofid id=1 balance 16,970,100 (figures can change later)

The user's independent parsing of three SQL backups showed:
- before-v126 (2026-10-26) and before-v129 (2026-10-28) both Takvin debt +47,520,000, no change in 3 payment total or 16 purchase total;
- before-v130 (2026-10-31) debt incorrectly +50,000,000 with same payment/purchase aggregates and last changed 2026-10-29 06:52:15.031509+00:00;
- real 50,000,000 bank transfer was made and the **software** payment was deleted because the old v21 `max(0,...)` clamp ate the overpayment credit.
The correct final balance is -2,480,000 (user owns a receivable from supplier). The 50M payment should exist exactly once in BusinessPayment, debiting the actual original bank once. No fresh physical payment should be initiated. Do not guess the source bank or exact payment date from backup cash totals alone; many other transactions occurred.

## Code
Parent: V130 successful source `f3323ef155c1ccc7290512f2a82cdc01ac060d2c`.
V131 adds only a new command `core/management/commands/recover_takvin_deleted_50m_v131.py`, isolated tests, guarded deploy, workflow/docs. NO model, finance logic, stock, or schema changes.
- Default `--bank melat|mofid --paid-on YYYY-MM-DD` is DRY_RUN: checks exact corrupt debt 50,000,000 and original updated timestamp; payment IDs and totals, purchase count/total, no prior v131 marker/50M active Takvin payment, distinct bank rows; prints expected after values and NEVER writes.
- `--apply --approval I_CONFIRM_REAL_50M_BANK_TRANSFER_AND_NO_DUPLICATE --expected-bank-balance <current value>` atomically resets erroneous debt to +47,520,000 and uses **canonical V130 v62 payment posting function** to insert one BusinessPayment 50,000,000 dated exactly as confirmed and sourced to bank confirmed by bank receipt. This means signed supplier after balance -2,480,000 and bank after = bank before -50,000,000. Other bank unchanged, payment count 4, marker `takvin-real-payment-recovery-v131`; guarded assertions roll back whole transaction on mismatch.
- `server_takvin_recovery_v131.sh` builds web, dumps full DB to backups, verifies protected hashes including Takvin debt setting and all BusinessPayments PRE=PROJECTED=FINAL, performs ONLY dry-run before/after deploy, never calls `--apply`. The financial repair is separate.
- `.github/workflows/check-takvin-recovery-v131.yml` builds production Docker and exercises disposable PostgreSQL tests for no-write dry-run, Mellat and Mofid debits, idempotency, prerequisite failure, rollback exception, plus past V126-V130.

## Operator workflow
1. Deploy guarded V131 after CI green; deployment does NOT change any money.
2. Verify actual receipt payment **bank** Mellat or Mofid and real transfer **date**. They are NOT recoverable with certainty from current snapshots.
3. Run `docker compose exec -T web python manage.py recover_takvin_deleted_50m_v131 --bank BANK --paid-on YYYY-MM-DD` (no --apply). Compare dry-run to current data.
4. Immediately before final financial repair, `source ./.env` and use `docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > backups/before-v131-Takvin-financial-recovery-....sql`, check nonempty, save.
5. With explicit user confirmation of the source/date/bank balance, run the exact guarded `--apply` invocation with `--expected-bank-balance` from fresh preview and approval token; do NOT run twice or try to double-pay.
6. Run `check_takvin_signed_v130` and Finance UI: should display signed -2,480,000 «طلب از تکوین», 4 active payment rows (including one 50M), bank source decreased by 50M from pre-recovery current accounting balance, other bank unchanged.
7. If any precondition differs, stop; don't forcibly overwrite or run outdated repair script.

IMPORTANT: signed debt is subtracted by `core/capital_history_v87.py`. The corrections should improve capital consistency without ad hoc formula changes. No other data may change.
