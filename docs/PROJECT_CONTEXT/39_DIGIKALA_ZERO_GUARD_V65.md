# 39 — DIGIKALA ZERO-STOCK TELEGRAM GUARD V65

Status at creation: GitHub-prepared SAFE MODE. Production is not confirmed until the user posts the final V65 success marker.

## User requirement

When a Darma color/size reaches zero in **combined internal inventory**:

```text
combined = HOME + KHORSHID
```

the existing Telegram inventory bot should notify the authorized user, for example:

```text
سفید / XL = 0
```

The user ultimately wants an approval action that can deactivate every Digikala variant for the same size whose Darma product depends on that color.

## V65 safety boundary

V65 is deliberately the read-only discovery/approval-preview phase.

It DOES:

- scan Darma combined stock about every 60 seconds;
- persist only zero/positive transition markers in AppSetting so restarts do not spam;
- seed currently-zero cells silently on the first bot scan after deploy;
- notify only when a cell later changes from positive to zero;
- provide a Telegram button to preview affected Digikala variants;
- GET current Digikala `/open-api/v1/variants`;
- resolve product identity exclusively from Digikala title text through `title_product_resolver_v27`;
- resolve size through the existing `SIZE_ALIASES` / `_resolve_size` path;
- handle variable-color Darma `s3` from the title color;
- display seller variant id, DKPC, active state, seller stock and Digikala warehouse stock.

V65 DOES NOT:

- call `PUT`, `PATCH` or business `POST` endpoints on Digikala;
- call `/variants/<id>/activation`;
- call `/variants/<id>/seller-stock` for mutation;
- deactivate any current Digikala product;
- change any internal SaleLine, SaleSnapshot, SaleAllocation, StockBalance or InventoryMovement;
- change accounting, capital, receivable, payments, returns, materials or production;
- use seller code to identify a product.

## Exact affected-product rule

For a fixed-composition Darma product and selected size:

- the product is affected only if its active ProductSize for that size exists;
- its ProductComposition contains the zero color with positive quantity;
- the current Digikala title resolves to that exact Darma product and size.

For variable-color `s3`:

- fixed composition is not invented;
- the selected color must be one of the supported title colors;
- the Digikala title itself must identify the same color and size.

Unknown or ambiguous titles fail closed and are reported as unresolved; they are never guessed.

## Zero transition semantics

Only combined owned Darma stock is watched:

```text
HOME + KHORSHID <= 0 -> zero
HOME + KHORSHID > 0  -> positive
```

A first V65 bot startup initializes marker state without sending a burst for historical zero cells.

After that:

```text
positive -> zero  => one Telegram alert
zero -> zero      => no repeat
zero -> positive  => marker reset
positive -> zero  => alert again
```

This is independent of the existing 09:00 grouped production/transfer alert.

## Telegram flow in V65

Zero alert:

```text
⛔ موجودی کل دارما صفر شد
سفید / XL
[بررسی کدهای متاثر]
[فعلاً کاری نکن]
```

Preview shows the real read-only mapping. The action button is explicitly locked:

```text
🔒 غیرفعال‌سازی فعلاً قفل است
```

A later version may enable real Digikala writes only after the user reviews actual VPS mapping output and explicitly authorizes the write phase.

## Existing bot/token architecture

The existing bot service remains `run_inventory_bot`.

V65 mounts only the existing Digikala runtime token directory into the bot:

```text
/opt/darma-secrets/digikala/runtime -> /run/secrets/digikala
```

The RSA private key is still not mounted.

## Regression

```bash
python manage.py check_digikala_zero_guard_v65
python manage.py check_digikala_zero_guard_v65 --live-map
```

The normal check uses synthetic title mapping and an atomic rollback zero-transition test.

`--live-map` performs GET-only current Digikala mapping and prints:

- total variants read;
- title/size resolution counts;
- Darma resolution count;
- unresolved Darma-like titles;
- current zero cells and how many active DK variants each would affect;
- `DIGIKALA WRITE CALLS = 0`.

## V59 regression correction carried with V65

The Novani resolver itself already filters by date. The old V59 regression incorrectly treated the literal cost 65,000 as proof of leakage on the prior date. That can false-fail if a legitimate earlier rule is also 65,000.

The regression is corrected to:

1. capture the exact prior-date cost before inserting a future test rule;
2. use a unique sentinel future cost;
3. assert the future date resolves to the sentinel;
4. assert the prior date remains exactly equal to its captured value.

No Novani accounting resolver or business rule is changed by this regression correction.

## Deployment

Rollback branch:

```text
before-digikala-zero-guard-v65-20260907
```

Deploy script:

```bash
bash server_digikala_zero_guard_v65.sh
```

Expected final marker:

```text
SUCCESS: DIGIKALA ZERO GUARD V65 SAFE MODE DEPLOYED
```

This marker confirms only the safe Telegram/read-only phase. It does NOT mean Digikala write/deactivation is enabled.


## V65 network-resilience patch

A production safe-mode run showed that `GET /open-api/v1/variants` can exceed the original 8-second read timeout.

The safe mapper now retries the same GET-only operation with increasing per-request timeouts:

```text
15s -> 30s -> 45s
```

with a short backoff between attempts.

If all read attempts still fail during deployment:

- deployment reports `LIVE DIGIKALA MAP DEFERRED`;
- deployment may continue because V65 contains no Digikala write path;
- the Telegram bot remains capable of zero-stock notifications;
- clicking the preview button later retries the GET path;
- any preview network failure returns a Telegram error message and performs zero Digikala changes.

This behavior is intentionally different from a future write-enabled phase: once real deactivation is ever introduced, successful live mapping and explicit user confirmation must become mandatory again before any write.

The deploy script also sets `COMPOSE_IGNORE_ORPHANS=1` only to suppress the harmless warning caused when the already-running Telegram bot exists outside a base-compose command. It does not remove or recreate an orphan by itself, and `--remove-orphans` is not used.
