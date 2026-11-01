/* V131 UI only. All POST actions retain V23 form data/endpoint semantics. */
(() => {
  'use strict';

  const groups = Array.from(document.querySelectorAll('.prod131-group'));
  const search = document.getElementById('prod131-search');
  const month = document.getElementById('prod131-month');
  const noResults = document.getElementById('prod131-no-results');

  const normalize = (s) => String(s ?? '')
    .replace(/[ي]/g, 'ی').replace(/[ك]/g, 'ک')
    .replace(/[\u200c\s]/g, '').toLowerCase()
    .replace(/[۰-۹]/g, d => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
  const number = (s) => {
    const v = normalize(s).replace(/[,٬]/g, '').replace(/[^0-9.-]/g, '');
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };
  const format = n => Math.round(n).toLocaleString('fa-IR');

  function visibleRows() {
    let shown = 0;
    const query = normalize(search?.value);
    groups.forEach(group => {
      const matches = !query || normalize(group.dataset.search).includes(query);
      group.hidden = !matches;
      if (matches) shown++;
    });
    if (noResults) noResults.hidden = shown > 0;
  }
  search?.addEventListener('input', visibleRows);
  month?.addEventListener('change', () => {
    const value = month.value;
    if (value) window.location.assign('?report_month=' + encodeURIComponent(value));
  });

  function toggle(group, open) {
    if (!group) return;
    const panel = group.querySelector('.prod131-detail');
    const btn = group.querySelector('.prod131-toggle');
    if (!panel || !btn) return;
    panel.hidden = !open;
    group.classList.toggle('is-open', open);
    btn.setAttribute('aria-expanded', String(open));
    if (open) {
      groups.forEach(other => { if (other !== group) toggle(other, false); });
    }
  }
  groups.forEach(group => {
    group.querySelector('.prod131-toggle')?.addEventListener('click', () => {
      toggle(group, group.querySelector('.prod131-detail').hidden);
    });
    group.querySelector('.prod131-close')?.addEventListener('click', () => toggle(group, false));
  });
  const anchor = String(window.location.hash || '').match(/^#block-(\d+)$/);
  if (anchor) {
    const group = groups.find(g => g.dataset.block === anchor[1]);
    if (group) toggle(group, true);
  }

  // Only a brand new roll gets the two 2.5 kg suggested values. Never
  // rewrite pre-existing material quantities or apply stock consumption.
  groups.forEach(group => {
    const code = group.querySelector('input[data-new-code]');
    if (!code) return;
    const initialCode = code.value.trim();
    let suggested = false;
    code.addEventListener('input', () => {
      if (suggested || initialCode || !code.value.trim()) return;
      ['elastic16', 'elastic25'].forEach(kind => {
        const field = group.querySelector('input[data-field="' + kind + '"]');
        if (field && !field.value.trim()) field.value = '2.5';
      });
      suggested = true;
    });
  });

  groups.forEach(group => {
    group.querySelectorAll('input.prod131-delivery,input[data-field="cut"]').forEach(input => {
      input.addEventListener('input', () => {
        const cut = number(group.querySelector('input[data-field="cut"]')?.value);
        const taken = Array.from(group.querySelectorAll('input.prod131-delivery'))
          .reduce((sum, field) => sum + Math.max(0, number(field.value)), 0);
        const amountCells = group.querySelectorAll('.prod131-main .prod131-num');
        if (amountCells.length >= 4) {
          amountCells[1].textContent = format(cut);
          amountCells[2].textContent = format(taken);
          amountCells[3].textContent = format(Math.max(0, cut - taken));
        }
        const summary = group.querySelector('.prod131-detail-header p');
        if (summary) {
          const original = summary.textContent || '';
          const appliedMatch = original.match(/اعمال‌شده\s+([\d۰-۹٬,]+)/);
          const applied = appliedMatch ? appliedMatch[1] : '—';
          summary.textContent = 'برش ' + format(cut) + ' · تحویل ' + format(taken)
            + ' · مانده ' + format(Math.max(0, cut - taken))
            + ' · اعمال‌شده ' + applied;
        }
        group.dataset.unsavedEdit = '1';
      });
    });
    group.querySelectorAll('.prod131-fields input,.prod131-fields select').forEach(input => {
      input.addEventListener('change', () => { group.dataset.unsavedEdit = '1'; });
    });
  });

  document.querySelectorAll('.prod131-open-dest').forEach(button => {
    button.addEventListener('click', () => {
      const el = document.getElementById(button.dataset.dialog);
      if (el && typeof el.showModal === 'function') el.showModal();
    });
  });
  document.querySelectorAll('.prod131-dialog-close').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });

  // Per-sheet metadata remains stored with its original POST names, even
  // though the editor for that sheet now appears below the first color row.
  document.querySelectorAll('.prod131-meta').forEach(field => {
    field.addEventListener('input', () => {
      const form = document.getElementById(field.dataset.form);
      const target = form?.elements.namedItem(field.dataset.meta);
      if (target) target.value = field.value;
    });
  });

  // The original V23 apply paths synchronize a whole sheet; make that explicit
  // when one visible color row belongs to a sheet with several color rows.
  document.querySelectorAll('form.prod131-hidden-form').forEach(form => {
    form.addEventListener('submit', event => {
      const submitter = event.submitter;
      if (!submitter) return;
      const target = submitter.getAttribute('formaction') || form.getAttribute('action') || '';
      const confirmText = submitter.dataset.confirm;
      if (confirmText && !window.confirm(confirmText)) {
        event.preventDefault();
        return;
      }
      if (!target.includes('/apply-output/')) return;

      const blockId = form.id.replace('material-form-', '');
      const siblingRows = groups.filter(group => group.dataset.block === blockId);
      const pendingEdits = siblingRows.filter(group => group.dataset.unsavedEdit === '1');
      const hasMultiple = siblingRows.length > 1;
      if (hasMultiple && !window.confirm(
        'این صورت ' + siblingRows.length + ' رنگ/کد دارد. همگام‌سازی، اختلاف تحویل تمام رنگ‌های همین صورت را اعمال می‌کند، نه فقط ردیف بازشده. ادامه می‌دهی؟'
      )) {
        event.preventDefault();
        return;
      }
      // No additional financial/inventory action is performed in JS.
      if (pendingEdits.length) form.dataset.lastAction = 'delivery';
    });
  });

  visibleRows();
})();
