(() => {
  const stripMoney = (value) => String(value ?? '').replace(/[٬٫,\s]/g, '').replace(/[^0-9.-]/g, '');
  const num = (value) => {
    const n = Number(stripMoney(value));
    return Number.isFinite(n) ? n : 0;
  };
  const fmt = (value) => {
    const rounded = Math.round(value || 0);
    const sign = rounded < 0 ? '-' : '';
    return sign + String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  };

  function recalc(row) {
    const qty = num(row.querySelector('.raw-quantity')?.value);
    const price = num(row.querySelector('.raw-unit-price')?.value);
    const total = qty * price;
    const output = row.querySelector('.raw-line-total');
    if (output) {
      output.textContent = fmt(total);
      output.dataset.value = String(Math.round(total));
    }
  }

  function bind(root = document) {
    root.querySelectorAll('.raw-calc-row').forEach((row) => {
      if (row.dataset.rawCalcBound === '1') return;
      row.dataset.rawCalcBound = '1';
      const inputs = row.querySelectorAll('.raw-quantity,.raw-unit-price');
      inputs.forEach((input) => input.addEventListener('input', () => recalc(row)));
      recalc(row);
    });
  }

  document.addEventListener('DOMContentLoaded', () => bind());
  document.body?.addEventListener('htmx:afterSwap', (event) => bind(event.target));
})();
