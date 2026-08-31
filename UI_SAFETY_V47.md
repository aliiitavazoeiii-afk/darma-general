# UI SAFETY V47 — BLACK / RED RUNTIME THEME

V47 is strictly presentation-only.

Allowed effects:

- black/charcoal/red CSS palette;
- sidebar logo plaque/background presentation;
- red active/hover/focus accents;
- comprehensive-report KPI layout alignment;
- responsive visual changes only.

Forbidden effects:

- any model/migration change;
- any route/view/business service change;
- any accounting, receivable, capital or valuation change;
- any inventory quantity/location change;
- any sale/import/allocation change;
- any payment/material/production/return/Digikala behavior change.

Deployment must capture the exact filtered economic snapshot before and after and require equality.

V47 is implemented as a runtime CSS overlay inside the web container. Tracked business/templates/CSS source remains unchanged. This makes rollback a clean web-container rebuild/recreate from current Git source.

Rollback command:

```bash
bash server_rollback_black_red_ui_v47.sh
```

Do not call V47 production-confirmed until the user posts:

```text
SUCCESS: BLACK RED UI V47 DEPLOYED
```
