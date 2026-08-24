(() => {
  const SEP = '٬';

  function raw(value) {
    const text = String(value ?? '').trim();
    const negative = text.startsWith('-');
    const digits = text.replace(/[٬٫,\s]/g, '').replace(/[^0-9]/g, '');
    return (negative ? '-' : '') + digits;
  }

  function grouped(value) {
    const cleaned = raw(value);
    if (!cleaned || cleaned === '-') return cleaned;
    const negative = cleaned.startsWith('-');
    const digits = negative ? cleaned.slice(1) : cleaned;
    const out = digits.replace(/\B(?=(\d{3})+(?!\d))/g, SEP);
    return (negative ? '-' : '') + out;
  }

  function bind(root = document) {
    root.querySelectorAll('input.money, input.money-input').forEach((input) => {
      if (input.dataset.groupBound === '1' || input.type === 'number') return;
      input.dataset.groupBound = '1';
      if (input.value) input.value = grouped(input.value);
      input.addEventListener('input', () => {
        const posFromEnd = input.value.length - (input.selectionStart || input.value.length);
        input.value = grouped(input.value);
        const next = Math.max(0, input.value.length - posFromEnd);
        try { input.setSelectionRange(next, next); } catch (_) {}
      });
    });
  }

  window.DarmaNumber = { raw, grouped, separator: SEP };
  document.addEventListener('DOMContentLoaded', () => bind());
  document.body?.addEventListener('htmx:afterSwap', (event) => bind(event.target));
})();
