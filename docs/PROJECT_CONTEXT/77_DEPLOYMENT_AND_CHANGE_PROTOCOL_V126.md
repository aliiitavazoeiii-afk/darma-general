# V126 PRODUCTION SAFETY, TESTS, DEPLOYMENT AND FUTURE-CHANGE PLAYBOOK
Last verified GitHub functional parent: `v126-payment-history-filters` @ `90a79e993adced1689c70d5b0777ce2ea7f2789f`, 2026-10-25. Handoff: 2026-10-26.
This file supersedes older instructions suggesting V37/V65/V108 is the latest development base. **Actual VPS runtime state still takes precedence.**

## Current status and unknowns
- The owner confirmed in conversation on Oct 26 that the V126 payment history filter "اوکی شد". Record as owner acceptance.
- V126 GitHub Action `40190753941` on SHA `90a79e99...` succeeded. CI proves code checks, NOT live runtime or true financial snapshot.
- Without fresh read-only server output one cannot assert current VPS HEAD, container image digest, schema migration state, current capital or inventory.
- Documentation-only branch `docs-v126-complete-handoff-1405-08` is NOT a functional deploy and contains no user credentials.

## Basic read-only inspection (when relevant)
~~~bash
cd /opt/darma-general
git status --short
git branch --show-current
git rev-parse HEAD
docker compose ps
docker compose exec -T web python manage.py check
~~~
Never print the server `.env`, Django secrets, passwords or SSH private keys. `git rev-parse HEAD` does not prove which baked image is running; inspect current container separately when necessary.

## Per-request development protocol
1. Identify exact user-visible feature, correct Jalali date, affected brand/color/location and ledger; check which older requirement has been superseded.
2. Trace current `core/urls.py` to active view/template and its imports, not the newest-numbered filename. Read the relevant history `75` and active map `76`, then current source and test.
3. Classify request: cosmetic/read-only, transaction-changing stock, financial/asset-changing, or historical data repair. Protect all unrelated invariants.
4. For disputed numbers, collect a read-only breakdown by saved row ID, cut/registered/applied, raw/finished material ledger, signed person accounts and exact value delta. Do not change current data on guesses.
5. Create feature branch from latest VERIFIED functional production lineage, not stale sibling or documentation branch. Keep existing backend services and form POST paths unless user explicitly requests a business change.
6. Implement minimal diff, tests for edge cases and exact forbidden side effects. Transaction-changing tests only on isolated test DB or rollback harness.
7. New guarded deployment script: exact parent SHA, strict allowlist, no unauthorized schema/ledger/model changes, backup, protected hash snapshots, read-only prechecks, production web-only restart and postchecks; explicit SUCCESS string.
8. Confirm the latest GitHub Actions run is green for the exact proposed HEAD. Offer precise server commands and expected marker; never claim production success before server/user confirmation.
9. On later success record date/version and any actual business-value snapshot; historical snapshots are NOT reset targets.

## Historic branch and deployment references
- Current accepted functional branch: `v126-payment-history-filters` @ `90a79e993adced1689c70d5b0777ce2ea7f2789f`.
- Current feature-specific deployment script: `server_payment_history_filters_v126.sh`. Marker `SUCCESS: V126 PAYMENT HISTORY FILTERS DEPLOYED` plus `PRE = PROJECTED = FINAL`.
- Older `server_material_archive_month_v125.sh`, `server_payment_colors_v124.sh`, `server_material_color_transfer_v123.sh`, `server_pedram_receivable_v121.sh` are historical; do not downgrade or blindly rerun after installing V126.
- Source code is baked into Docker image: `git pull` alone does not update web container.
- Docker Hub may return CloudFront 403. V124–V126 guarded scripts can build equivalent Python 3.12 base through approved alternate registries without editing Dockerfile/Caddyfile. Never skip validation or silently edit Compose server config.

The next new feature will need **its own** matching tested deploy script. Generic template (placeholders are NOT literal runnable shell input):

~~~bash
cd /opt/darma-general
git fetch origin
git status --short
git switch FEATURE_BRANCH || git switch --track origin/FEATURE_BRANCH
git pull --ff-only origin FEATURE_BRANCH
bash server_NEW_FEATURE.sh
~~~

## Safety verification pattern
- Preserve local Caddyfile SHA256 before and after; no unwanted domain changes.
- PostgreSQL backup with `pg_dump` before migration/mutation; preserve path.
- `makemigrations --check --dry-run` and `python manage.py check`.
- Verify prerequisite migration `0020_novani_wholesale` and `0021_material_color_use_v123` applied where relevant, but do not silently migrate during a read-only phase.
- Check V121 Pedram repair in PREVIEW mode if installer requires; **never** auto-run its `--apply` during an unrelated feature.
- Protected business-state hash snapshots PRE/PROJECTED/FINAL compare exact quantities and critical account, material, sale, payment, ledger rows for read-only deployments; stop on unexplained difference.
- Run feature read-only audit on freshly built candidate image, then restart web ONLY after checks, and compare live hash again.
- Check neither current stock, bank balance nor capital changed for a GET/filter/template-only release. Do not enforce hash equality when user expressly authorized a known one-time accounting change; verify exact expected delta and reversals instead.
- If a guarded precheck fails, stop and diagnose; never simply delete a guard or replay a repair until its DB commit state is known.

## Stable read-only diagnostic examples (inspect source and running branch first)
~~~bash
cd /opt/darma-general
docker compose exec -T web python manage.py check_material_transfer_v123
docker compose exec -T web python manage.py check_inventory_alert_v123
docker compose exec -T web python manage.py check_payment_colors_v124
docker compose exec -T web python manage.py check_material_archive_month_v125
docker compose exec -T web python manage.py check_receipt_filters_v91
docker compose exec -T web python manage.py check_payment_filters_v126
~~~
Notes: `check_material_net_v122` validates valuable same-color signed math, but documents V122's OLD now-revoked carryover behavior; V123/V125 controls current/archived reporting. `check_fabric_roll_count_v116` is the V118 raw-roll coded/lifetime-weight audit, not necessarily identical to final month-only KPI.

## Regression matrix
**Report filters**: inclusive Jalali start/end, malformed/reversed dates, zero matches, all-time totals computed on ALL rows, pagination does not alter aggregate, receipt V91 unchanged; GET no writes.

**Month archives**: present Jalali month does not include old dates; clicking old month opens archived sheets and swaps its KPI, returns to current; historic debts include fabric-applied but unfinished-output colors, all custom colors, net rolls within each color only; old sheet save keeps same selected month.

**Single-color material apply**: one of five colors applied while others untouched, shared elastic allocated exactly, reapply idempotent, old bulk ledger attribution mismatches abort; inventory raw TAILOR decreases, but no finished-output/wage posting.

**Finished output**: saved delivery versus applied ledger separated, two-way delta application and reversal, output location HOME/KHORSHID chosen at apply, wage delta correct and insufficient reverse stock aborts atomically.

**Inventory**: HOME sales only per V46, bidirectional transfers preserve total and capital with source stock guard; blank stock correction unchanged vs typed zero exact zero; color-cell strong red exactly 0, soft red 1..9, normal >=10.

**Finance**: only actual `BusinessPayment.amount` sums for payments; material purchase goods value separated from paid bank amount; edit/delete restores both sides via canonical services; V121 signed Pedram +gross, wage -delta; Novani sale does not reduce Darma stock.

**Schema**: no extra migration without request; tests creating objects must run on disposable Django test database, never production DB. Read-only diagnostic should not call get_or_create that can mutate.

## High-risk prohibited unattended actions
- One-time historical reset/reconciliation or end-31-Mordad/day-3-Shahrivar physical stock rebase;
- Direct delete of already applied BusinessPayment, SaleLine, sale snapshot, warehouse stock/purchase ledger, posted wholesale invoice;
- Re-running Pedram V121 +2×gross repair without exact preview, ID check and owner approval;
- Enabling Digikala seller-side writes, automatic KHORSHID->HOME sale transfers (V46 prohibition), or rewriting accounting percentages;
- Mistaking payment form display for authority to post unsupported raw-material colors; raw-fabric versus finished-output actions must remain distinct;
- Running any historical server script only because its file still exists.

## Error response playbook
Record failed step, preceding backup and whether DB writes were possible. Determine if script only built or already migrated/restarted/applied mutations. Inspect compose status / limited sanitized logs. Do not rerun a financial mutation before confirming exact persistence. If rollback required, get user authorization for exact point-in-time data restoration.

## Next update of this handoff
After approved V127+: add numbered `docs/PROJECT_CONTEXT/NN_FEATURE_V127.md` with new user rule, precisely which older rule it superseded, route/code map, tests, screenshots only if available, branch/commit, guarded script, successful CI and **actual** deployment evidence. Update `AI_START_HERE.md` and the new chat prompt. Avoid silently editing old historic notes in place, because they are forensic history.
