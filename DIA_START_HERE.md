# DIA_START_HERE

This document is the source-of-truth entry point for branch `dia`.

## Identity

- Product: **Dia Gallery**
- Production domain: `samaneh.filmjadiid.ir`
- Active Django app: `dia_core`
- Active Django settings: `config.settings`
- Docker Compose project: `dia-gallery`
- Server path: `/opt/dia-gallery`

## Critical isolation rule

Branch `dia` was created from the historical `darma-general` repository only to reuse visual/engineering ideas. The old `core/` tree is **legacy reference code and is NOT part of the Dia Gallery runtime**.

Do not import from `core` into `dia_core`.
Do not enable the old `core` app.
Do not run old Darma/Takvin migrations, seed commands or deployment scripts.
Do not mount or reuse any `/opt/darma-*` path, database, PostgreSQL volume, `.env`, API token, Telegram token, backup or secret.

All new Dia Gallery work must be implemented in `dia_core` (plus shared project config/templates/deployment files when necessary).

## Active features

- dark RTL dashboard and responsive/mobile navigation
- Jalali daily sales calendar
- manual daily sales entry
- local Digikala commission calculation (NO Digikala API)
- sales / commission / COGS / profit reports
- independent finished-goods inventory ledger
- purchase-of-the-day workflow
- returns
- inventory adjustment
- independent accounts, payments and receipts
- product / variant / size / color definitions

## Explicitly absent/disabled

- Darma catalog or data
- Takvin catalog, purchases, debt or pricing rules
- Material Report and raw-material production workflow
- Darma production/tailor/fabric/elastic logic
- HOME/KHORSHID rules
- Anbaresh/Novani logic
- Dia-as-a-customer-of-Darma legacy workflow
- Digikala Open API client/routes
- Digikala API token mounts
- Telegram bot/alerts
- Digikala XLSX/API report importer
- any production data copied from the reference project

## Fresh database contract

`python manage.py seed_base` is allowed to create only:

1. stock location `main` / `موجودی اصلی`
2. local Digikala commission parameters
3. low-stock threshold

It must not seed products, sizes, colors, sales, inventory balances, accounts or personal/business data.

## Digikala commission

The commission formula is intentionally preserved as a local calculation in `dia_core.services.digikala_fee_for_unit`. It performs no network request. Its parameters are editable from Dia Gallery settings.

## Deployment

Use branch `dia` only. `deploy.sh` clones it to `/opt/dia-gallery`, creates a new `.env`, uses DB/user `dia_gallery`, and starts isolated volumes prefixed `dia_gallery_*`.

A GitHub commit does not mean production changed. Production is confirmed only after the VPS output contains:

`SUCCESS: DIA GALLERY BASE DEPLOYED`

## Future ChatGPT instruction

Read this file first, then `dia_core/models.py`, `dia_core/services.py`, `dia_core/views.py`, `dia_core/urls.py`, `config/settings.py`, `compose.yml` and `deploy.sh`.

Treat everything under legacy `core/` as inactive historical reference unless the owner explicitly asks to inspect it. Never copy business-specific logic from it into Dia Gallery by assumption.
