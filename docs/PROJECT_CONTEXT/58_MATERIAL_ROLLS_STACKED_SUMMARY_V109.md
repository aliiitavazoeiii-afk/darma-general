# V109 — MATERIAL ROLL COUNTS + STACKED SHEET SUMMARY

Base branch: `stable-final-2026-10-04`

## Five base-color cards

The existing five open-work cards (black, white, navy, pink, cream) keep the same:
- expected delivery from saved cut;
- actually applied finished delivery;
- pending quantity.

V109 adds `تعداد طاقه تحویلی` above those three metrics.

Roll counting intentionally follows the existing monthly material KPI semantics:
- one unique non-empty fabric code = one roll;
- an open-work row with positive weight and no fabric code = one roll;
- counting scope is the exact same OPEN work used by that color card (`cut > applied output`);
- completed historical sheets are excluded from these operational cards.

## Material-sheet collapsed summary

The existing sheet summary badges remain the same data and same bar/pill concept:
1. brand -> destination;
2. used models;
3. fabric codes;
4. material apply state;
5. applied delivery;
6. pending increase/reduction when present.

V109 changes presentation only:
- badges are stacked vertically, one per line;
- text grows from 0.69rem to 0.84rem;
- badge width remains content-sized;
- padding is kept compact so the badges themselves are not visually inflated.

No material consumption/output/accounting/inventory mutation logic changes.

## Regression

`python manage.py check_material_rolls_stacked_v109`

Required marker:
`SUCCESS: MATERIAL ROLLS + STACKED SUMMARY V109 CHECK PASSED`

Production marker:
`SUCCESS: MATERIAL ROLLS + STACKED SUMMARY V109 DEPLOYED`

After production confirmation, the canonical stable baseline should be fast-forwarded to this V109 commit before starting further features.
