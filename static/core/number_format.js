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

    // V97: Finance & Tools is one direct destination, not an expandable submenu.
    nav.querySelectorAll('[data-business-tools-nav]').forEach((node) => node.remove());
    const legacyFinanceGroup = [...nav.querySelectorAll('.erp-nav-group')].find((group) =>
      (group.querySelector('.erp-nav-group-title')?.textContent || '').trim() === 'مالی و ابزار'
    );
    const path = window.location.pathname;
    const financeActive = path.startsWith('/finance/') || path.startsWith('/payments/') || path.startsWith('/calculator/');
    const financeLink = document.createElement('a');
    financeLink.dataset.financeRootNav = '1';
    financeLink.href = '/finance/';
    financeLink.className = financeActive ? 'active' : '';
    financeLink.innerHTML = '<span class="erp-dot"></span>مالی و ابزار';
    if (legacyFinanceGroup) {
      legacyFinanceGroup.replaceWith(financeLink);
    } else if (!nav.querySelector('[data-finance-root-nav]')) {
      definitionsTitle.parentNode.insertBefore(financeLink, definitionsTitle);
    }
  }

  function injectV39Styles() {
    if (document.getElementById('darma-ui-v39')) return;
    const link = document.createElement('link');
    link.id = 'darma-ui-v39';
    link.rel = 'stylesheet';
    link.href = '/static/core/ui-v39.css?v=39';
    document.head.appendChild(link);
  }

  // V94: this file is already included by base.html on every ERP page.
  // Load the Jalali calendar once from here so all date inputs share one picker.
  function injectGlobalJalaliPicker() {
    if (window.__darmaJalaliPickerLoading || window.__darmaJalaliPickerLoaded) return;
    window.__darmaJalaliPickerLoading = true;
    const script = document.createElement('script');
    script.id = 'darma-global-jalali-picker-v94';
    script.src = '/static/core/jalali_picker.js?v=94';
    script.async = false;
    script.onload = () => { window.__darmaJalaliPickerLoading = false; };
    script.onerror = () => { window.__darmaJalaliPickerLoading = false; };
    document.head.appendChild(script);
  }

  // Presentation-only default. The inventory POST handlers and stock mutation
  // code remain untouched; this only selects Darma in the existing adjustment UI.
  function defaultInventoryAdjustmentToDarma() {
    if (window.location.pathname !== '/inventory/operations/') return;
    const select = document.getElementById('adjust-brand');
    if (!select || select.dataset.v94DefaultApplied === '1') return;
    const darma = [...select.options].find((option) => (option.textContent || '').trim() === 'دارما');
    if (!darma) return;
    select.dataset.v94DefaultApplied = '1';
    select.value = darma.value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  injectV39Styles();
  injectGlobalJalaliPicker();
  window.DarmaNumber = { raw, grouped, separator: SEP };
  document.addEventListener('DOMContentLoaded', () => {
    bind();
    injectToolNav();
    defaultInventoryAdjustmentToDarma();
  });
  document.body?.addEventListener('htmx:afterSwap', (event) => bind(event.target));
})();
