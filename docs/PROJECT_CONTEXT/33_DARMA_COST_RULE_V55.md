# V55 — CENTRALIZED DATE-EFFECTIVE DARMA COST + SHAHRIVAR REPAIR

## Authoritative user rule

Darma has exactly one accounting cost per short. The cost is not color-dependent and not size-dependent.

There must be one user-facing source of truth with an effective date. Example only:

```text
through 1405/06/14: 61,000 toman per short
from    1405/06/15: 67,000 toman per short
```

When a rule is entered for a date, every Darma-backed report on or after that effective date must follow the date-rule history. Reports before the effective date stay unchanged.

The currently owned Darma inventory is always valued at the rate effective today. Therefore a new rule that is effective today may legitimately revalue finished inventory and capital immediately.

## Root cause of the 18,549 discrepancy

Before V55, Darma accounting had conflicting sources:

- the intended generic/current Darma cost around 61,000;
- `InventoryModelCost` per Darma color + size.

`core/inventory_valuation_v17.py` used the color/size model costs for current Darma stock, while `core/cost_accounting_v14.py` also averaged actual allocated color costs into some new Darma/Anbaresh SaleSnapshots.

That is why a 3-pack return of pack5 / M = 15 shorts could increase current finished inventory by 933,549 instead of:

```text
15 * 61,000 = 915,000
```

The 18,549 difference was not a fee. It was color/size cost drift.

## Single source of truth

New service:

`core/darma_cost_v55.py`

Rules are controlled `AppSetting` rows:

`darma_cost_rule_YYYY-MM-DD`

No schema migration is required.

Confirmed/protected baseline:

```text
1400/01/01 -> 61,000 toman per short
```

The baseline cannot be deleted or overwritten through the user-facing rule action. To change cost, the user adds a later effective date.

`darma_cost_for(on_date)` selects the newest rule with `effective_from <= on_date`.

The older `darma_accounting_unit_cost` setting remains backend fallback only for a database with no dated rule. It is hidden from the generic settings table so there is only one visible Darma cost control.

## Rule application semantics

User-facing `apply_darma_cost_rule(effective_from, unit_cost)` is atomic:

1. save/update the date-effective rule;
2. re-evaluate existing Darma/Anbaresh SaleSnapshot `unit_cost` rows on or after that date using the complete rule history;
3. re-evaluate existing Dia Gallery `unit_cost` rows on or after that date;
4. leave all dates before the effective date untouched.

This changes COGS/profit reporting only. It does not change sale quantity, sale price, Digikala fee, receivables, StockBalance, InventoryMovement or AccountEntry.

Deleting a non-baseline rule similarly recalculates affected later rows from the remaining rule history.

Missing Darma/Anbaresh SaleSnapshots are not created during general rule repricing. `sale_line_metrics()` has a canonical date-effective fallback, so those reports still follow the new rule without freezing unrelated fee/pack fields.

## Active accounting paths

### Darma / Anbaresh / s3 SaleSnapshot

`core/cost_accounting_v14.py`

- Darma -> `darma_cost_for(line.day.date)`
- Anbaresh -> same Darma rule because it is Darma-backed
- variable-color `s3` is a Darma SaleLine and therefore uses the same rate
- no Darma `InventoryModelCost` averaging remains
- Takvin stays on `takvin_cost_for()`

### Daily report / missing snapshot fallback

`core/finance.py`

If a Darma/Anbaresh SaleLine lacks a usable snapshot, `sale_line_metrics()` uses `darma_cost_for(line.day.date)` instead of ProductSize cost.

This closes the legacy/missing-snapshot path that could otherwise reintroduce a second Darma cost.

### Current finished inventory / capital

`core/inventory_valuation_v17.py`

Every current Darma short across HOME + KHORSHID is valued using the single rate effective today.

A current-rate change therefore revalues current finished inventory/capital by exactly:

```text
current Darma total qty * (new current rate - previous current rate)
```

This is inventory revaluation, not sale profit and not cash.

`InventoryModelCost` is no longer an accounting source for Darma.

### Standalone returns and physical corrections

`core/returns_v37.py` remains physically unchanged: a standalone return adds positive HOME stock and creates no sale/cash/Digikala entry.

Because current Darma valuation is central, returning N Darma shorts changes current finished inventory/capital by exactly:

```text
N * current effective Darma cost
```

Thus 15 shorts at 61,000 = exactly 915,000.

### Dia Gallery

`core/dia_gallery_v45.py`

New Dia rows freeze `darma_cost_for(line.day.date)` into `DiaGallerySale.unit_cost`. Existing rows on/after a newly entered effective date are repriced by the central rule service.

### Bulk Darma sale-price compatibility

`core/darma_pricing.py`

The old hardcoded ProductSize compatibility cost `61000` was removed. When bulk sale prices create/update ProductSize rows, the compatibility `unit_cost` is aligned to `darma_cost_for()`.

This field is not the Darma accounting source of truth after V55.

## User interfaces

### Settings -> Rules and base prices

`core/settings_rules_v17.py`
`templates/core/settings_rules_v17.html`

The Darma card contains:

- effective Jalali date;
- one cost per Darma short;
- current effective rate;
- rule history;
- protected baseline badge;
- guarded delete for later rules.

When a rule is saved, the message reports how many SaleSnapshots and Dia rows were repriced from that date onward.

### Product definition/edit form

`templates/core/settings_product_form.html`

Darma no longer exposes per-size accounting-cost controls as a competing source. When Darma is selected:

- the cost columns are hidden;
- the old `بهای دارما 61 000` fill button is gone;
- the page links directly to `قوانین محاسبات` as the central cost reference.

The hidden legacy ProductSize inputs remain submitted unchanged for backward data compatibility, but Darma accounting does not read them as its source.

## Targeted repair — only 12 and 14 Shahrivar 1405

Command:

`repair_darma_cost_shahrivar_v55`

Dry-run is default. `--apply` is explicit.

Repair scope:

- active Darma/Anbaresh/s3 SaleLines on `1405/06/12` and `1405/06/14`;
- active Dia Gallery rows on the same two dates.

It changes only:

- `SaleSnapshot.unit_cost`;
- `DiaGallerySale.unit_cost`.

If a target normal SaleLine unexpectedly has no SaleSnapshot, the targeted repair may create one using its existing pack quantity and the canonical existing Digikala fee, then freeze the correct Darma unit cost.

It does NOT change:

- sale quantity;
- sale price;
- Digikala fee formula;
- Digikala receivable;
- Dia receivable;
- StockBalance quantity;
- AccountEntry;
- payments;
- transfers;
- adjustments;
- any other date.

Expected repair marker:

`SUCCESS: DARMA COST SHAHRIVAR V55 REPAIR APPLIED`

## Regression

Command:

`check_darma_cost_rule_v55`

Rollback-only checks verify:

- date-effective rule resolution;
- baseline protection;
- Darma/Anbaresh/s3 snapshots use canonical sale-date cost;
- missing-Snapshot fallback is canonical;
- existing reports on/after a new effective date reprice while earlier snapshots stay unchanged;
- Dia follows the same effective-date rule;
- current inventory revalues by exact Darma qty * rate delta;
- return/adjustment valuation is exact qty * current Darma rate;
- product form contains no independent Darma cost control;
- bulk Darma pricing contains no independent 61,000 accounting hardcode;
- all regression test writes roll back.

Expected marker:

`SUCCESS: DARMA COST RULE V55 CHECK PASSED`

## Deployment safety

Rollback branch:

`before-darma-cost-rule-v55-20260905`

Base commit:

`f97f157f7206bcec0340789d822ca17e05888980`

Deploy script:

`server_darma_cost_rule_v55.sh`

The script:

1. takes a pg_dump backup;
2. captures old business state;
3. computes the old Darma color/size valuation and expected 61,000 central valuation;
4. builds the new image;
5. runs migration drift, Django, V37, V48, V50, V51, V52, V53, V54 and V55 checks;
6. verifies preflight wrote no business data;
7. seeds the protected 61,000 baseline;
8. dry-runs and applies only the 12+14 Shahrivar repair;
9. verifies repair moved no physical/financial ledgers;
10. recreates live web;
11. verifies target-day canonical costs;
12. verifies FINISHED/CAPITAL changed only by the exact expected Darma revaluation and all other business invariants stayed unchanged.

The deploy script is retry-safe if a previous attempt already recreated the V55 image.

Final required markers:

`SUCCESS: DARMA COST RULE V55 DEPLOYED`

`SUCCESS: DARMA COST SHAHRIVAR V55 REPAIR APPLIED`

Do not call V55 production-confirmed until the user posts these actual VPS markers/output.
