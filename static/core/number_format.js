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

  function injectToolNav() {
    const nav = document.querySelector('.erp-nav');
    if (!nav) return;
    const definitionsTitle = [...nav.querySelectorAll('.erp-nav-title')].find((el) =>
      (el.textContent || '').trim() === 'تعاریف'
    );
    if (!definitionsTitle) return;

    if (!nav.querySelector('[data-returns-nav]')) {
      const path = window.location.pathname;
      const link = document.createElement('a');
      link.dataset.returnsNav = '1';
      link.href = '/returns/';
      link.className = path.startsWith('/returns/') ? 'active' : '';
      link.innerHTML = '<span class="erp-dot"></span>مرجوعی';
      definitionsTitle.parentNode.insertBefore(link, definitionsTitle);
    }

    if (!nav.querySelector('[data-digikala-nav]')) {
      const path = window.location.pathname;
      const link = document.createElement('a');
      link.dataset.digikalaNav = '1';
      link.href = '/digikala/';
      link.className = path.startsWith('/digikala/') ? 'active' : '';
      link.innerHTML = '<span class="erp-dot"></span>دیجی‌کالا';
      definitionsTitle.parentNode.insertBefore(link, definitionsTitle);
    }

    if (nav.querySelector('[data-business-tools-nav]')) return;
    const wrap = document.createElement('div');
    wrap.dataset.businessToolsNav = '1';
    const path = window.location.pathname;
    const payActive = path.startsWith('/payments/');
    const calcActive = path.startsWith('/calculator/');
    wrap.innerHTML = `
      <div class="erp-nav-title">مالی و ابزار</div>
      <a class="${payActive ? 'active' : ''}" href="/payments/"><span class="erp-dot"></span>پرداختی‌ها</a>
      <a class="${calcActive ? 'active' : ''}" href="/calculator/"><span class="erp-dot"></span>محاسبه‌گر</a>
    `;
    definitionsTitle.parentNode.insertBefore(wrap, definitionsTitle);
  }

  function injectV39Styles() {
    if (document.getElementById('darma-ui-v39')) return;
    const link = document.createElement('link');
    link.id = 'darma-ui-v39';
    link.rel = 'stylesheet';
    link.href = '/static/core/ui-v39.css?v=39';
    document.head.appendChild(link);
  }

  injectV39Styles();
  window.DarmaNumber = { raw, grouped, separator: SEP };
  document.addEventListener('DOMContentLoaded', () => {
    bind();
    injectToolNav();
  });
  document.body?.addEventListener('htmx:afterSwap', (event) => bind(event.target));
})();
