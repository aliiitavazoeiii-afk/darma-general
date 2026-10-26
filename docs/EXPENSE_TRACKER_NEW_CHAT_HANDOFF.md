# Darma Expense Tracker — NEW CHAT HANDOFF

> READ THIS FILE FIRST BEFORE MAKING ANY CHANGE.
>
> Repository: `aliiitavazoeiii-afk/darma-general`
>
> Branch: `expense-tracker-v1`
>
> Production domain: `https://kharj.filmjadiid.ir`
>
> Expense worktree: `/opt/darma-expense`
>
> Main ERP worktree: `/opt/darma-general`
>
> Dedicated Compose project: `darma-expense`
>
> Dedicated service: `expense-web`
>
> Expense host debug port: `8011`
>
> Isolation base commit: `40ba4293dcd7b05fedef33f37f70ebcbeedd8655`

## 0. Why this file exists

This is the full continuation/handoff document for the isolated Darma personal expense tracker ("خرج من"). It records the design decisions, financial semantics, deployment isolation, version history, regressions, production incidents, and the exact rules that must be preserved.

A new chat/engineer must not start by guessing from the UI. Read this file, then read `docs/EXPENSE_TRACKER_V1.md`, then inspect the live branch files named below.

The expense tracker intentionally lives in the same repository/database ecosystem as Darma General, but it is a separate Django site, separate worktree, separate Docker Compose project and separate web container. The most important invariant is: expense work must not silently mutate or redeploy unrelated ERP business logic.

## 1. Current source-of-truth hierarchy

When facts conflict, use this order:

1. Current code on branch `expense-tracker-v1`.
2. This handoff file.
3. `docs/EXPENSE_TRACKER_V1.md`.
4. Commit history.
5. Chat memory.

Never assume GitHub HEAD is already live in production. Production is confirmed only by server output after a successful guarded deployment, or by direct live diagnostics.

Operational code baseline immediately before this documentation handoff was:

`7998d03e47ef370071b2b2f5cd5b053fad2a6dfe`

Documentation commits after that SHA can move branch HEAD without changing runtime behavior.

## 2. Critical production-status caveat

As of the latest incident discussed before this handoff:

- the expense site had become unresponsive while the Docker container still appeared `Up`;
- port 8011 was listening, but HTTP requests hung;
- manually restarting only `darma-expense-expense-web-1` restored both local and public responses to HTTP 302;
- logs showed Gunicorn restarted normally after that manual restart;
- the production worktree `/opt/darma-expense` had previously reported:
  `fatal: not a git repository: /opt/darma-general/.git/worktrees/darma-expense`
- a `git worktree repair /opt/darma-expense` was recommended, but successful repair + full guarded deployment of the latest hardening commits was NOT confirmed in the chat before this handoff.

Therefore: before the next code deployment, first verify that the worktree is valid and check exactly which commit/image is running. Do not state that the latest GitHub hardening is live unless server evidence proves it.

## 3. Repository and runtime architecture

The expense tracker is isolated inside the Darma General repository.

Primary expense paths:

- `expense_site/` — separate Django settings/urls/wsgi.
- `expense_tracker/` — models, views, services, regressions, reporting/export.
- `templates/expense_tracker/` — expense UI.
- `static/expense_tracker/` — expense JS/CSS/icons.
- `Dockerfile.expense`
- `compose.expense.yml`
- `expense_entrypoint.sh`
- `server_expense_tracker_v1.sh`
- `docs/EXPENSE_TRACKER_V1.md`
- `docs/EXPENSE_TRACKER_NEW_CHAT_HANDOFF.md`

Main ERP protected paths that must remain byte-unchanged relative to the expense branch base unless the user explicitly starts a separate ERP task:

- `core/`
- `config/`
- `compose.yml`
- `compose.telegram.yml`
- `Caddyfile`
- main `entrypoint.sh`
- `templates/core/`
- `static/core/`

One intentional shared bridge already exists in protected ERP code:

`core.payment_source_v63`

Expense code uses this bridge to read/mutate canonical account rows for Mellat and Mofid. Do not duplicate account balances inside the expense app.

## 4. Database and business boundary

The expense site uses the same PostgreSQL database as Darma General, through the existing Docker DB network. It has its own `expense_tracker` tables/migrations but intentionally reads/writes the canonical Mellat/Mofid account rows.

Expense tracker must NOT create or mutate unrelated ERP ledgers such as:

- `BusinessPayment`
- `SaleLine` / sales allocations/snapshots
- `InventoryMovement`
- `StockBalance`
- Digikala settlement/receivable accounting
- production/material rows
- valuation/cost rules
- Takvin purchase/business data

The deployment script snapshots key ERP business values before migration/tests/deploy and compares them after every phase.

## 5. Authoritative expense financial semantics — V7

Model: `DailyExpense`

Each expense stores:

- Gregorian date
- amount
- category
- payment source: Mellat or Mofid
- title
- note
- timestamps

Payment-source constants:

- `melat` → ملت
- `mofid` → مفید

Historical expenses created before dual-account V7 were migrated to Mellat because all old expense cash effects had been applied to Mellat.

All expense cash mutations are atomic and lock canonical source rows.

### Create expense

`selected_source -= amount`

### Edit expense, same source

`selected_source += old_amount - new_amount`

### Edit expense and change source

`old_source += old_amount`

`new_source -= new_amount`

### Delete expense

`stored_source += deleted_amount`

Do not "simplify" these semantics. They were regression-tested specifically to prevent money drift.

## 6. Receivables financial semantics — V5

Models:

- `ReceivablePerson`
- `ReceivableEntry`

Kinds:

- claim / طلب
- payment / تسویه

A new claim means real money left Mellat and is now owed back:

`Mellat -= claim.amount`

A real repayment means money came back:

`Mellat += repayment.amount`

Deleting a repayment reverses that credit.

Deleting a new claim restores its original debit only if the row actually affected Mellat.

Historical compatibility is controlled by:

`ReceivableEntry.mellat_applied`

Historical claims created before V5 are intentionally left `mellat_applied=False`, so deleting an old claim cannot falsely increase Mellat.

Do not retroactively mark old claims applied unless the accounting history is explicitly audited.

## 7. Initial and current category behavior

Initial categories were:

- غذا
- VPN
- کار
- ماشین
- تفریح
- روزمره

Users can add more categories.

A category that already has expenses should not be destructively deleted; deactivate it instead. Category names are unique.

## 8. Dashboard behavior

The current top dashboard KPIs are:

1. خرج امروز
2. میانگین خرج روزانه
3. خرج این هفته
4. خرج ماه جاری شمسی

Daily average means:

`current Jalali month expense total / elapsed Jalali calendar days through today`

This intentionally includes zero-spend days.

The dashboard shows canonical Mellat balance, but does NOT show a dedicated Mofid balance card.

Quick expense entry defaults to Mellat, with Mofid available as an explicit payment-source option.

After successful AJAX save:

- Mellat dashboard balance updates if applicable;
- today/week/month totals update;
- daily average updates from the month total;
- recent-expense list gets the new row;
- amount/title/note clear;
- selected date remains;
- selected category remains;
- selected payment source remains;
- manual page reload resets normal defaults.

## 9. Jalali/backdated entry — UI V2

The expense site has a dedicated Jalali calendar route:

`/calendar/picker/`

The quick-entry date is a readonly Jalali-picker field.

Backdated expenses are supported.

Important rapid-entry workflow:

- choose a past date once;
- enter multiple expenses;
- AJAX save should not navigate/scroll;
- selected date/category/payment source remain for the next entry;
- only amount/title/note clear.

The calendar JS comes from existing shared static core:

`static/core/jalali_picker.js`

The expense branch must not modify `static/core` merely for this app.

## 10. PWA history and current V9 policy

PWA endpoints:

- `/manifest.webmanifest`
- `/sw.js`

The app is installable and has 192px/512px icons.

### Historical V3/V8 behavior

Older service workers cached expense JS/CSS under un-hashed paths such as:

- `/static/expense_tracker/app.js`
- `/static/expense_tracker/app.css`
- `/static/expense_tracker/v7.css`

At the same time Django/WhiteNoise-generated HTML referenced fingerprinted assets such as:

`app.<hash>.js`

This created a risk that installed/PWA clients kept a stale frontend while HTML referenced a newer version.

### Current V9 source behavior

Current `expense_tracker/pwa.py` uses cache:

`kharj-man-shell-v9`

The service worker caches only expense icons. It deliberately does NOT cache:

- authenticated HTML
- financial endpoints
- JS
- CSS

Current `static/expense_tracker/app.js` registers the service worker with:

`updateViaCache: "none"`

and explicitly asks for `registration.update()`.

This was introduced after intermittent browser symptoms:

- Jalali calendar sometimes did not open;
- AJAX save showed `Failed to fetch`;
- browser behavior did not always match current server code.

Do not reintroduce JS/CSS precaching without a carefully versioned strategy.

## 11. Safe behavior on AJAX network failure

A dangerous idea was explicitly rejected: automatically retrying an expense POST after a `fetch()` network error.

Reason: the first POST may have reached the server and committed successfully even if the response was lost. An automatic retry could double-record the expense and double-debit an account.

Therefore the current frontend gives a clearer network-error message and tells the user to refresh/check recent transactions before submitting again.

Preserve this no-auto-retry safety property.

## 12. Transactions V7

Main route:

`/expenses/`

Filters/search run across full history.

The top "جمع نتایج" is scoped to the current Jalali month only.

Previous matching months remain available in collapsed historical sections.

Historical months expand into day groups.

There is no intentional 250-row truncation in the V7 routed transaction implementation; routing goes through `expense_tracker.expense_v7`, not the older fallback implementation still present in `views.py`.

When reading code, be careful not to confuse old compatibility functions in `views.py` with the V7 routed functions.

## 13. Category detail reports V8

Routes:

- `/reports/category/<id>/`
- `/reports/category-name/<name>/`

The name route exists because dashboard/report summary rows historically exposed the category name directly. Category names are unique.

Dashboard category rows and report category rows are clickable/tappable via `bindCategoryReports()` in `static/expense_tracker/app.js`.

Each category report shows:

- current Jalali month total/count;
- all-time total/count;
- largest recorded expense;
- top five largest expenses sorted descending;
- rank/progress visualization;
- full history grouped by Jalali month;
- current month open by default;
- older months collapsible;
- day groups inside each month;
- title/note/date/amount/payment source;
- edit link;
- link to filtered transactions.

The category report is read-only and must not change Mellat/Mofid.

### V8 regression incident history

The V8 regression itself caused several deploy failures even though feature logic was mostly correct:

1. It attempted full template render before `collectstatic`, and WhiteNoise manifest storage failed on icon lookup.
2. It used a fragile literal Persian phrase check (`همه خرج‌های این دسته`) while the template correctly used dynamic `{{ category.name }}`.
3. Live render used a fake authenticated user without `username`, while `base.html` accesses `request.user.username`.

These were corrected by:

- deferring manifest-dependent full render until live post-`collectstatic` phase;
- checking structural template markers rather than brittle exact wording;
- making the regression user fixture expose realistic username/short-name behavior.

Lesson: regression guards must test behavior without becoming more brittle than production code.

## 14. Reports and financial export V6/V7

Reports route:

`/reports/`

Financial export:

`/reports/export.xlsx`

The XLSX contains five sheets:

1. `هزینه‌ها`
2. `گردش طلب‌ها`
3. `خلاصه ماهانه`
4. `خلاصه دسته‌ها`
5. `وضعیت فعلی`

V7 includes payment source in expense export and both Mellat/Mofid current balances.

The exporter protects user-controlled text against Excel formula injection.

`openpyxl` is installed only in `Dockerfile.expense`; the main ERP dependency file is intentionally not modified for this feature.

## 15. Main files to read before changing behavior

Always read current versions of these files before edits:

- `docs/EXPENSE_TRACKER_NEW_CHAT_HANDOFF.md`
- `docs/EXPENSE_TRACKER_V1.md`
- `expense_tracker/models.py`
- `expense_tracker/services.py`
- `expense_tracker/views.py`
- `expense_tracker/expense_v7.py`
- `expense_tracker/category_report_v8.py`
- `expense_tracker/export_xlsx.py`
- `expense_tracker/urls.py`
- `expense_tracker/pwa.py`
- `templates/expense_tracker/base.html`
- `templates/expense_tracker/dashboard.html`
- `templates/expense_tracker/expenses.html`
- `templates/expense_tracker/category_report.html`
- `static/expense_tracker/app.js`
- `static/expense_tracker/app.css`
- `static/expense_tracker/v7.css`
- `compose.expense.yml`
- `expense_entrypoint.sh`
- `server_expense_tracker_v1.sh`

## 16. Migrations

Important expense migrations include:

- initial expense/receivable schema;
- receivable `mellat_applied` compatibility migration;
- `DailyExpense.payment_source` migration.

Historical payment source migration defaults old expenses to Mellat.

Do not generate unrelated migrations.

Deploy script runs:

`makemigrations --check --dry-run`

and fails on migration drift.

## 17. Regression commands and expected invariants

Base regression:

`python manage.py check_expense_tracker_v1 --settings=expense_site.settings`

Checks include:

- dashboard daily-average marker;
- PWA/manifest/service-worker properties;
- Jalali calendar route;
- AJAX expense save;
- Mellat create/edit/delete reconciliation;
- receivable historical safety;
- new claim/repayment cash effects;
- no leaked persistent business changes.

V7 regression:

`python manage.py check_expense_v7 --settings=expense_site.settings`

Checks include:

- Mofid create/edit/delete;
- source switch Mofid → Mellat;
- current-month search total;
- previous-month archive.

V8 category regression:

`python manage.py check_expense_category_report_v8 --settings=expense_site.settings`

Checks include:

- structural template markers;
- current-month vs all-time totals;
- largest-expense order;
- Jalali month grouping;
- dashboard/report click wiring;
- by-id and by-name routes;
- live template render after production static manifest exists;
- Mellat/Mofid unchanged.

Export regression command name remains:

`python manage.py check_expense_export_v6 --settings=expense_site.settings`

Expected current marker references V7 export behavior.

All regression-generated business records must be inside rollback-only transactions or read-only paths.

## 18. Guarded deployment pipeline

Canonical deploy script:

`server_expense_tracker_v1.sh`

Do not bypass it casually.

High-level sequence:

1. verify main directories/env;
2. start/verify main DB/web without recreating ERP web unnecessarily;
3. discover main Docker network;
4. database backup;
5. snapshot protected ERP state;
6. verify expense branch changed-path isolation;
7. build isolated expense image;
8. migration drift check;
9. Django check;
10. apply only `expense_tracker` migrations;
11. verify protected ERP state unchanged;
12. run rollback regressions;
13. verify state unchanged;
14. recreate only expense web container;
15. run live checks/regressions;
16. compare final protected ERP snapshot;
17. print success.

Do NOT use Docker `--remove-orphans` for this project.

## 19. Protected-state snapshot

The deploy guard compares important ERP values including:

- capital
- Mellat
- Mofid
- finished inventory value
- raw materials
- Digikala receivable
- Dia Gallery receivable
- Takvin debt
- Darma/Takvin/Novani inventory quantities
- sales count
- payments count
- receipts count
- raw-material row count
- inventory movement count
- Takvin purchase count

If a supposedly isolated expense change alters these unexpectedly, deployment must fail.

Expected expense cash changes inside regressions are rolled back before snapshots are compared.

## 20. Caddy/network architecture

Main Caddy configuration contains:

`kharj.filmjadiid.ir { reverse_proxy expense-web:8000 }`

Caddy reaches expense-web through the shared Docker network by service name. It does NOT need the host port 8011.

The host port exists only as a local/debug path.

### Hardening added after Gunicorn hang incident

Current GitHub `compose.expense.yml` defaults the host binding to:

`127.0.0.1:8011:8000`

instead of public:

`0.0.0.0:8011:8000`

Reason: logs showed internet scanners directly hitting Gunicorn on the exposed host port, including malformed request lines. Since Caddy already proxies internally, public exposure of 8011 was unnecessary.

Do not reopen 8011 publicly unless there is a specific reason.

## 21. Gunicorn hang incident and hardening

Production had repeated incidents where:

- Docker reported `expense-web` as Up;
- TCP port 8011 was listening;
- HTTP requests connected but hung with no response;
- other sites on the same server remained healthy;
- restarting only `darma-expense-expense-web-1` immediately restored local and public HTTP responses.

This strongly indicated an application worker hang rather than server-wide failure, DNS failure, or Caddy failure.

Older entrypoint used:

- Gunicorn `gthread`
- 2 workers
- 2 threads
- timeout 60

Current GitHub hardening changed it to:

- `worker-class sync`
- 3 workers
- timeout 60
- graceful timeout 20
- `max-requests 250`
- `max-requests-jitter 50`
- worker temp dir `/dev/shm`

Purpose:

- make timeout enforcement more predictable;
- recycle workers periodically;
- reduce risk of a long-lived wedged worker pool;
- isolate stuck requests.

Important: source hardening existing on GitHub is not proof that the running container has been rebuilt from it.

## 22. Worktree incident

The intended production layout uses a Git worktree:

- main: `/opt/darma-general`
- expense: `/opt/darma-expense`

At one point:

`git -C /opt/darma-expense rev-parse HEAD`

failed with:

`fatal: not a git repository: /opt/darma-general/.git/worktrees/darma-expense`

This means the working directory existed but Git worktree metadata was missing/broken.

Recommended non-destructive first repair:

`cd /opt/darma-general && git worktree repair /opt/darma-expense`

Then verify:

`git worktree list`

`git -C /opt/darma-expense status`

`git -C /opt/darma-expense rev-parse --abbrev-ref HEAD`

`git -C /opt/darma-expense rev-parse HEAD`

Do not immediately `rm -rf /opt/darma-expense` or reclone while production data/runtime is being diagnosed. The database is shared and persistent, but careless replacement can obscure what image/code was actually running.

## 23. Fast production diagnostic checklist

If site is down while other server sites are up:

### A. Container and port

`docker ps -a --filter name=darma-expense-expense-web`

`ss -ltnp | grep ':8011' || true`

### B. Local HTTP with correct Host

`curl --max-time 5 -sS -o /dev/null -H 'Host: kharj.filmjadiid.ir' -w "LOCAL: HTTP %{http_code} | %{time_total}s\n" http://127.0.0.1:8011/`

### C. Public HTTP

`curl --max-time 5 -k -sS -o /dev/null -w "PUBLIC: HTTP %{http_code} | %{time_total}s\n" https://kharj.filmjadiid.ir/`

Normal unauthenticated result can be HTTP 302 to login.

### D. Logs

`docker logs --tail=200 darma-expense-expense-web-1 2>&1`

If local hangs but port is listening, suspect Gunicorn/app worker hang.

A temporary recovery that worked:

`docker restart darma-expense-expense-web-1`

Then re-run local/public curl checks.

Restart only the expense container; do not restart unrelated ERP containers merely because the expense site is down.

## 24. Historical version timeline

### V1 — isolated runtime and deployment

- separate Django site;
- separate worktree/container/compose project;
- shared DB;
- guarded deploy;
- backup + ERP invariant snapshots;
- expense/receivable basics.

Representative commits:
- `f20c7d5f47b7` add isolated expense tracker runtime
- `ecb2a7ce9a35` guarded isolated deployment
- `d349bee720cb` final isolation audit

### V2 — quick-entry UI / Jalali / AJAX

- Jalali picker;
- backdated entry;
- no-refresh save;
- preserve date/category;
- UI redesign;
- AJAX regression.

Representative commits:
- `f1c3c8b20494`
- `ccf494e5da1e`
- `78bdd5e7bdea`
- `d39f0860a33a`
- `a3cc99306df8`

### V3 — PWA / install / day grouping

- icons;
- manifest;
- service worker;
- Android install;
- grouped transaction days.

Representative commits:
- `7e4404ef1847`
- `b6e138cc087c`
- `239f9de51eb7`
- `cc1ef8119015`
- `20fe43235a86`

### V4 — temporary daily revenue dashboard experiment

- added read-only ERP daily gross revenue;
- temporarily replaced a dashboard KPI;
- later superseded by V5;
- helper remains harmless/read-only.

### V5 — receivable cashflow + elapsed-month daily average

- claims debit Mellat;
- repayments credit Mellat;
- historical compatibility via `mellat_applied`;
- daily-average KPI.

Representative commits:
- `b1f25e965787`
- `6c93aeff32e9`
- `70a6a049d1db`
- `381b2afc6abe`
- `81bf42ecc0cc`

### V6 — financial XLSX export

- five-sheet workbook;
- formula-injection protection;
- current-state financial snapshot;
- read-only export regression.

Representative commits:
- `656492fc62f6`
- `55fe283f9f32`
- `88b920b99e4f`
- `6ef8f8b4db6b`

### V7 — Mellat/Mofid dual account + monthly transaction archives

- per-expense payment source;
- historical expenses → Mellat;
- Mofid-safe create/edit/delete;
- source switching;
- payment source in export;
- search across history;
- current-month top total;
- previous months collapsed.

Representative commits:
- `64accff27f89`
- `cebb8be9993a`
- `c9558ab22652`
- `9f8f610d51c0`
- `0df11f15dd3d`
- `2c5e2804f82d`
- `ffca59902405`
- `fe6a9f98f04b`
- `918cc50fa0df`
- `782e015e0b3f`

### V8 — detailed category reports

- clickable category rows;
- dedicated report;
- top-five expenses;
- current/all-time totals;
- Jalali month archive;
- V8 deployment regression.

Representative commits:
- `e26e5f8a2e44`
- `07db3cae7173`
- `4a7c9ddcc058`
- `0424fd48bcfe`
- `6bf34e17aa3b`
- `fd836ae06e7c`
- `feed874e5317`
- `eab67e971bce`

Regression robustness fixes:
- `a739dc6e14d2`
- `7b9d1140249a`

### V9 — PWA stale-cache prevention

- stop service-worker caching JS/CSS;
- bump shell cache to V9;
- force SW update without HTTP cache;
- safer network-error messaging;
- regression guard against reintroducing JS/CSS precache.

Representative commits:
- `44fb5787fd05`
- `dd191f7d7deb`
- `871bf0aa3480`

### Post-V9 runtime hardening

- sync workers + recycle;
- loopback-only host debug port.

Representative commits:
- `bd0aa8aa547f`
- `7998d03e47ef`

## 25. UI/UX expectations to preserve

The user expects the expense site to feel fast and simple, especially on mobile.

Important expectations:

- Persian-first interface.
- Jalali calendar.
- Dark visual theme.
- Quick repeated entry.
- Thousands separators.
- Search and category drill-down.
- Current month and historical context both visible.
- No accidental scroll/navigation after quick save.
- Categories easy to tap.
- Financial source (ملت/مفید) visible where relevant.
- No Mofid top balance card unless explicitly requested.

## 26. Safety rules for future changes

1. Never silently change financial semantics.
2. Never infer that an expense should affect some ERP ledger besides canonical Mellat/Mofid.
3. Never retry financial POSTs automatically after ambiguous network failure.
4. Never remove historical compatibility fields merely because they look redundant.
5. Never use `--remove-orphans`.
6. Never recreate the main ERP web container as part of ordinary expense changes.
7. Never edit protected main ERP paths on this isolated branch unless the task explicitly requires a coordinated ERP change.
8. Always preserve rollback-only regressions.
9. Always inspect current branch file contents before edits.
10. Always distinguish "pushed to GitHub" from "deployed and verified in production".
11. When production is down, diagnose local service vs Caddy vs browser cache before changing code.
12. Do not expose port 8011 publicly; Caddy reaches the service internally.

## 27. Recommended first actions for a new chat

Before making any new feature/fix:

1. Read this file and `docs/EXPENSE_TRACKER_V1.md`.
2. Read current branch ref/HEAD.
3. Inspect current versions of the main files listed in section 15.
4. Compare `40ba429...` to current HEAD and confirm only approved expense paths changed.
5. If the task touches production, verify:
   - worktree validity;
   - current server commit if possible;
   - current container image/start time;
   - local/public HTTP health.
6. If changing money logic, add/extend rollback regression before deployment.
7. Use `server_expense_tracker_v1.sh` for deployment.
8. Do not claim success until final deploy marker and live health are confirmed.

## 28. Copy/paste prompt for a fresh ChatGPT conversation

Use this as the first message in a new chat:

---

I want to continue my Darma Expense Tracker project.

Repository:
`aliiitavazoeiii-afk/darma-general`

Branch:
`expense-tracker-v1`

Production:
`https://kharj.filmjadiid.ir`

Server paths:
- main ERP: `/opt/darma-general`
- expense tracker: `/opt/darma-expense`

Before giving any recommendation or changing any code, read these files completely from the `expense-tracker-v1` branch:

1. `docs/EXPENSE_TRACKER_NEW_CHAT_HANDOFF.md`
2. `docs/EXPENSE_TRACKER_V1.md`
3. `expense_tracker/models.py`
4. `expense_tracker/services.py`
5. `expense_tracker/expense_v7.py`
6. `expense_tracker/category_report_v8.py`
7. `expense_tracker/export_xlsx.py`
8. `expense_tracker/urls.py`
9. `expense_tracker/pwa.py`
10. `static/expense_tracker/app.js`
11. `templates/expense_tracker/dashboard.html`
12. `templates/expense_tracker/category_report.html`
13. `compose.expense.yml`
14. `expense_entrypoint.sh`
15. `server_expense_tracker_v1.sh`

Also inspect the current branch HEAD and the diff from base commit:
`40ba4293dcd7b05fedef33f37f70ebcbeedd8655`

Important rules:
- this is an isolated expense site sharing the Darma PostgreSQL DB;
- do not alter unrelated ERP business logic;
- protected ERP paths must stay unchanged;
- canonical Mellat/Mofid rows are the only intentional financial bridge;
- preserve all V5/V7 financial semantics and rollback regressions;
- never automatically retry a financial POST after an ambiguous network failure;
- do not use Docker `--remove-orphans`;
- do not confuse a GitHub commit with confirmed production deployment;
- before production deployment verify the `/opt/darma-expense` worktree is valid;
- production previously suffered Gunicorn hangs where the container was Up but HTTP hung; current GitHub includes sync-worker/recycle hardening and loopback-only port 8011, but verify whether that code is actually deployed before assuming it is live.

After reading everything, first give me a short state summary:
1. current GitHub HEAD;
2. current architecture;
3. financial invariants you must preserve;
4. latest known production issue/state;
5. any unresolved deployment/worktree risk.

Then continue from my next request without redesigning the project from scratch.

---

## 29. Final reminder

This project is financially sensitive even though it is small. The most valuable property is not UI polish; it is exact reconciliation with canonical Mellat/Mofid plus strong isolation from the main Darma ERP.

Prefer small, auditable changes with explicit regressions over broad rewrites.
