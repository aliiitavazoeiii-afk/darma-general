(() => {
  const stripMoney = (value) => String(value ?? '').replace(/[٬٫,\s]/g, '').replace(/[^0-9.-]/g, '');
  const num = (value) => {
    const n = Number(stripMoney(value));
    return Number.isFinite(n) ? n : 0;
  };
  const fmtMoney = (value) => {
    const rounded = Math.round(value || 0);
    const sign = rounded < 0 ? '-' : '';
    return sign + String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  };

  function recalc(row) {
    const qty = num(row.querySelector('.raw-quantity')?.value);
    const price = num(row.querySelector('.raw-unit-price')?.value);
    const out = row.querySelector('.raw-line-total');
    if (out) out.textContent = fmtMoney(qty * price);
  }

  function bindCalc(root = document) {
    root.querySelectorAll('.raw-calc-row').forEach((row) => {
      if (row.dataset.rawCalcBound === '1') return;
      row.dataset.rawCalcBound = '1';
      row.querySelectorAll('.raw-quantity,.raw-unit-price').forEach((input) => {
        input.addEventListener('input', () => recalc(row));
      });
      recalc(row);
    });
  }

  function bindPicker(root = document) {
    const panel = root.querySelector?.('#raw-materials') || document.querySelector('#raw-materials');
    if (!panel || panel.dataset.pickerBound === '1') return;
    panel.dataset.pickerBound = '1';

    const kindButtons = [...panel.querySelectorAll('[data-raw-kind]')];
    const locationButtons = [...panel.querySelectorAll('[data-raw-location]')];
    const locationPicker = panel.querySelector('#rawLocationPicker');
    const panes = [...panel.querySelectorAll('[data-pane]')];
    let kind = '';

    const hidePanes = () => panes.forEach((pane) => pane.classList.add('d-none'));
    const clearLocation = () => locationButtons.forEach((btn) => btn.classList.remove('active'));

    kindButtons.forEach((btn) => btn.addEventListener('click', () => {
      kind = btn.dataset.rawKind;
      kindButtons.forEach((b) => b.classList.toggle('active', b === btn));
      clearLocation();
      hidePanes();
      locationPicker?.classList.remove('d-none');
      locationPicker?.scrollIntoView({behavior:'smooth', block:'nearest'});
    }));

    locationButtons.forEach((btn) => btn.addEventListener('click', () => {
      if (!kind) return;
      clearLocation();
      btn.classList.add('active');
      hidePanes();
      const pane = panel.querySelector(`[data-pane="${kind}-${btn.dataset.rawLocation}"]`);
      pane?.classList.remove('d-none');
      pane?.scrollIntoView({behavior:'smooth', block:'nearest'});
    }));
  }

  function bind(root = document) {
    bindCalc(root);
    bindPicker(root);
  }

  document.addEventListener('DOMContentLoaded', () => bind());
  document.body?.addEventListener('htmx:afterSwap', (event) => bind(event.target));
})();
