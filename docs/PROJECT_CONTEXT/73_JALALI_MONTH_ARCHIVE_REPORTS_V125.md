# V125 — Per-Jalali-month archived Material Reports

Branch: `v125-material-month-archive-reports`, forked from V124 `v124-dynamic-payment-fabric-colors` at commit `1cc238e7570ed43c89ae47f6bafe596b0846fb4c`.

## User request

Current Aban 1405 reporting must remain zero/current-only when no new unapplied materials exist. When opening a **previous month's collapsed month archive** (e.g. Mehr 1405), show that **month's own production/material KPI and color progress** above the archived sheet list — all without bringing older sheets back into current-month totals or expanding them by default.

An archive report also needs to expose **unfinished sewing deliveries after fabric was already applied**, because the current V123 raw-unapplied-only KPI intentionally excludes those colors.

## Implementation

- New `_past_month_dashboard_reports(objects, current_month)` in `core/material_report_v92.py`: groups by each sheet's original **Jalali date**, outputs previous months descending. No current/future rows or carryover in previous month scopes. Uses existing `_current_unapplied_material_metrics(month_blocks)` exactly as current top KPIs do for monthly unconsumed raw fabric and five main colors. No change to V123 current-month logic or formulas.
- New `_archive_delivery_status(month_blocks)`: separately computes **all brand/color cut vs saved receipt vs applied finished-goods stock**, including color rolls whose fabric was already consumed. Net surplus and deficit **within** each color before clamping, never across colors/brands. Fields: expected, delivered, applied, pending, surplus, awaiting_stock_apply, fabric_unapplied. Grouped by month and brand/color.
- New read-only Django partial `templates/core/_material_month_archive_report_v125.html`: monthly KPI, five main-color cards, and independent all-color delivery detail table; reports clarify that they reflect **latest saved/applied data**, not a frozen month-end snapshot. Useful for continuing deliveries entered in Aban against Mehr invoices.
- `templates/core/material_report_v92.html` places these pre-rendered partials in an inert HTML `<template>`; existing JS creating collapsed past-month `<details>` clones **only the matching month** into its archive body. Archived reports remain invisible until their month opens. No interaction modifies persisted records. New archive layout uses existing card styles.
- `check_material_archive_v125` read-only verifier: synthetic Mehr pink 750+750 cuts, saved 998+540=1538, applied=1233, net surplus 38; white cut 120/received 40 yet fabric already applied still flagged as 80 overdue; another completed color; isolated Shahrivar and Aban values; updates after further saved receipt; Django templates and JS integration markers. Live mode prints each archived month status, does not alter DB.
- GitHub Actions `check-material-month-archive-v125.yml` verifies Django, synthetic data, HTML templates and JS syntax on commits to the branch.

## Safety

- No migration, edits to finance, raw stock, stock synchronization, payment parser, wholesale/receivables, inventory, base.html, Caddyfile or existing material-report save/apply endpoint.
- Guarded deployment `server_material_archive_v125.sh` extends the approved V124 safety checks: database backup, protected data hash PRE/PROJECTED/FINAL, Caddyfile hash, vetted diff allowlist and migration check, CI-equivalent synthetic and read-only live audits, web-only recreation.
- Historical metrics are **not immutable snapshots**: user updates a Mehr delivery in Aban and Mehr archive refreshes on next page load. A true historical point-in-time reconstruction would require dated versioned snapshots, not supplied by the current tables.
- Main dashboard remains V123's strict **current Jalali month + only not-applied fabric colors**; archive outstanding output independently includes colors already applied at raw-material level.
