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

  const colorChoices = Array.from(document.querySelectorAll('.prod131-color-choice'));
  const materialChoices = Array.from(document.querySelectorAll('.prod131-status-choice'));
  let selectedColor = 'all';
  let selectedMaterial = 'all';

  const scopedMetric = (key, value, unit) => {
    const el = document.querySelector('[data-scope-metric="' + key + '"]');
    if (!el) return;
    el.textContent = value;
    if (unit) {
      const small = document.createElement('small');
      small.textContent = ' ' + unit;
      el.append(small);
    }
  };

  function visibleRows() {
    let shown = 0;
    const query = normalize(search?.value);
    const summary = {
      rolls: 0, weight: 0, cut: 0, entered: 0, remaining: 0, surplus: 0,
      costTotal: 0, costCut: 0, validWeight: 0, validCut: 0
    };
    groups.forEach(group => {
      const matchesColor = selectedColor === 'all' || group.dataset.color === selectedColor;
      const matchesSearch = !query || normalize(group.dataset.search).includes(query);
      const matchesMaterial = selectedMaterial === 'all' || (
        group.dataset.materialStatus === selectedMaterial &&
        group.dataset.materialMeaningful === '1'
      );
      const matches = matchesColor && matchesSearch && matchesMaterial;
      group.hidden = !matches;
      if (!matches) return;
      shown++;
      const weight = Math.max(0, number(group.dataset.weight));
      const cut = Math.max(0, number(group.dataset.cut));
      const entered = Math.max(0, number(group.dataset.entered));
      const countable = group.dataset.countable === '1' || weight > 0 || cut > 0 || entered > 0;
      // Empty draft-color editors appear in the table but are not production.
      if (!countable) return;
      summary.rolls++;
      summary.weight += weight;
      summary.cut += cut;
      summary.entered += entered;
      summary.remaining += number(group.dataset.remaining);
      summary.surplus += number(group.dataset.surplus);
      summary.costTotal += number(group.dataset.costTotal);
      if (cut > 0) summary.costCut += cut;
      if (cut > 0 && weight > 0) {
        summary.validCut += cut;
        summary.validWeight += weight;
      }
    });
    if (noResults) noResults.hidden = shown > 0;

    // The cards above the table always describe this exact filtered view.
    scopedMetric('rolls', format(summary.rolls));
    scopedMetric('weight', summary.weight.toLocaleString('fa-IR', {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    }), 'کیلو');
    scopedMetric('cut', format(summary.cut));
    scopedMetric('entered', format(summary.entered));
    scopedMetric('remaining', format(summary.remaining));
    scopedMetric('yield', summary.validWeight
      ? format(summary.validCut * 20 / summary.validWeight) : '—');
    scopedMetric('average_cost', summary.costCut
      ? format(summary.costTotal / summary.costCut) : '—', 'تومان');
    scopedMetric('total_cost', format(summary.costTotal), 'تومان');

    const rowCount = document.getElementById('prod137-row-count');
    const cutCount = document.getElementById('prod137-cut-count');
    if (rowCount) rowCount.textContent = format(summary.rolls);
    if (cutCount) cutCount.textContent = format(summary.cut);
    const colorLabel = selectedColor === 'all' ? 'همه رنگ‌ها'
      : (colorChoices.find(button => button.dataset.colorFilter === selectedColor)?.textContent || selectedColor).trim();
    const materialLabel = selectedMaterial === 'applied' ? 'مصرف اعمال‌شده'
      : selectedMaterial === 'unapplied' ? 'مصرف اعمال‌نشده' : 'همه وضعیت‌های مصرف';
    const descriptor = document.getElementById('prod137-filter-description');
    if (descriptor) descriptor.textContent = 'محدوده: ' + colorLabel + '، ' +
      materialLabel + (search?.value?.trim() ? '، جست‌وجوی «' + search.value.trim() + '»' : '') +
      ' در ماه انتخاب‌شده.';
  }
  materialChoices.forEach(button => {
    button.addEventListener('click', () => {
      selectedMaterial = button.dataset.materialFilter || 'all';
      materialChoices.forEach(choice => {
        const active = choice === button;
        choice.classList.toggle('selected', active);
        choice.setAttribute('aria-pressed', String(active));
      });
      visibleRows();
    });
  });
  colorChoices.forEach(button => {
    button.addEventListener('click', () => {
      selectedColor = button.dataset.colorFilter || 'all';
      colorChoices.forEach(choice => {
        const active = choice === button;
        choice.classList.toggle('selected', active);
        choice.setAttribute('aria-pressed', String(active));
      });
      visibleRows();
    });
  });
  search?.addEventListener('input', visibleRows);
  month?.addEventListener('change', () => {
    const value = month.value;
    const archived = month.dataset.mode === 'archive';
    if (value) window.location.assign(
      (archived ? '?mode=archive&report_month=' : '?report_month=') + encodeURIComponent(value)
    );
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
        const remaining = Math.max(0, cut - taken);
        const surplus = Math.max(0, taken - cut);
        if (amountCells.length >= 4) {
          amountCells[1].textContent = format(cut);
          amountCells[2].textContent = format(taken);
          const balance = amountCells[3];
          balance.textContent = surplus ? '+' + format(surplus) : format(remaining);
          balance.classList.toggle('is-pending', remaining > 0);
          balance.classList.toggle('is-surplus', surplus > 0);
          balance.classList.toggle('is-zero', remaining === 0 && surplus === 0);
        }
        group.dataset.cut = String(cut);
        group.dataset.entered = String(taken);
        group.dataset.remaining = String(remaining);
        group.dataset.surplus = String(surplus);
        visibleRows();
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


  // V138: send save and home/khorshid delivery to the existing V23 handlers
  // through a JSON adapter. No navigation, no HTML replacement, no scroll-to.
  // The open editor, focus, size inputs and all other unsaved entries survive.
  const inlineToast = document.getElementById('prod138-save-toast');
  let toastTimer = null;
  let pendingInlineRequest = false;

  function inlineNotice(message, kind) {
    if (!inlineToast) return;
    inlineToast.textContent = String(message || '');
    inlineToast.dataset.kind = kind || 'ok';
    inlineToast.hidden = false;
    if (toastTimer) window.clearTimeout(toastTimer);
    // Errors remain visible longer so ambiguous connectivity is not missed.
    toastTimer = window.setTimeout(() => { inlineToast.hidden = true; },
      kind === 'error' ? 9000 : 5200);
  }

  function inlineUpdateRow(group, state) {
    if (!group || !state) return;
    const props = {
      search: state.search,
      weight: state.weight,
      cut: state.cut,
      entered: state.entered,
      remaining: state.remaining,
      surplus: state.surplus,
      costTotal: state.cost_total,
      unitCost: state.unit_cost,
      materialStatus: state.material_applied ? 'applied' : 'unapplied',
      materialMeaningful: state.material_meaningful ? '1' : '0',
      countable: state.production_meaningful ? '1' : '0'
    };
    Object.entries(props).forEach(([key, value]) => {
      group.dataset[key] = String(value == null ? '' : value);
    });

    const cells = Array.from(group.querySelectorAll('.prod131-main > td'));
    if (cells.length >= 7) {
      const code = cells[0].querySelector('.prod131-code strong');
      if (code) code.textContent = state.code || 'بدون کد';
      cells[1].textContent = state.weight || '—';
      cells[2].textContent = format(number(state.cut));
      cells[3].textContent = format(number(state.entered));
      const remaining = Number(state.remaining) || 0;
      const surplus = Number(state.surplus) || 0;
      cells[4].textContent = surplus ? '+' + format(surplus) : format(remaining);
      cells[4].classList.toggle('is-pending', remaining > 0);
      cells[4].classList.toggle('is-surplus', surplus > 0);
      cells[4].classList.toggle('is-zero', remaining === 0 && surplus === 0);
      cells[5].textContent = number(state.unit_cost) ? format(number(state.unit_cost)) : '—';

      const status = cells[6];
      const pending = status.querySelector('.prod131-state.pending');
      if (state.dirty_stock) {
        if (!pending) {
          const badge = document.createElement('span');
          badge.className = 'prod131-state pending';
          badge.textContent = 'تحویل منتظر ثبت در انبار';
          badge.title = 'تعداد ثبت‌شده هنوز به موجودی خانه یا خورشید اضافه نشده است';
          status.prepend(badge);
        }
      } else {
        pending?.remove();
      }
      const material = status.querySelector('.prod131-mat-state');
      if (material) {
        material.textContent = state.material_applied
          ? 'مصرف مواد اعمال‌شده' : 'مصرف مواد اعمال‌نشده';
        material.classList.toggle('is-applied', Boolean(state.material_applied));
        material.classList.toggle('is-unapplied', !state.material_applied);
      }
    }
    const heading = group.querySelector('.prod131-detail-header p');
    if (heading) heading.textContent = 'برش ' + format(number(state.cut))
      + ' · تحویل ' + format(number(state.entered))
      + ' · مانده ' + format(number(state.remaining))
      + ' · اعمال‌شده ' + format(number(state.applied));
    const cost = group.querySelector('.prod131-size-head > span b');
    if (cost) cost.textContent = format(number(state.unit_cost)) + ' تومان';
  }

  function lockSheetDelete(blockId) {
    groups.filter(group => group.dataset.block === blockId).forEach(group => {
      const section = group.querySelector('.prod131-sheet-delete');
      if (!section || section.classList.contains('is-locked')) return;
      section.classList.add('is-locked');
      const button = section.querySelector('button');
      if (button) {
        button.disabled = true;
        button.textContent = 'حذف صورت غیرفعال';
        button.removeAttribute('onclick');
      }
      const note = section.querySelector('span');
      if (note) note.textContent = 'حذف این صورت مسدود است، چون موجودی یا مواد اولیه آن اعمال شده است.';
    });
  }

  document.querySelectorAll('form.prod131-hidden-form[data-inline-url]').forEach(form => {
    // The existing V131 listener runs first (including important confirmations).
    form.addEventListener('submit', async event => {
      if (event.defaultPrevented) return;
      const submitter = event.submitter;
      const target = submitter?.getAttribute('formaction') || form.getAttribute('action') || '';
      const isDelivery = target.includes('/apply-output/');
      const isSave = !submitter?.getAttribute('formaction') && target.includes('/save/');
      if (!isDelivery && !isSave) return; // Keep add-model/materials legacy behavior.

      event.preventDefault(); // Never navigate or cause a page refresh.
      if (pendingInlineRequest) {
        inlineNotice('ثبت قبلی هنوز در حال انجام است؛ دوباره ارسال نکن.', 'error');
        return;
      }
      const inlineUrl = form.dataset.inlineUrl;
      if (!inlineUrl) {
        inlineNotice('مسیر ذخیره بدون رفرش یافت نشد؛ هیچ درخواستی ارسال نشد.', 'error');
        return;
      }

      const body = new FormData(form); // Also collects externally associated fields.
      if (submitter?.name) body.append(submitter.name, submitter.value);
      body.set('_inline_action', isDelivery ? 'apply-output' : 'save');
      const fingerprint = JSON.stringify(Array.from(new FormData(form).entries()));
      const blockId = form.id.replace('material-form-', '');
      const buttons = Array.from(document.querySelectorAll(
        'button[form="' + form.id + '"], .prod131-open-dest[data-dialog^="prod131-dialog-' + blockId + '-"]'
      ));
      pendingInlineRequest = true;
      buttons.forEach(button => { button.disabled = true; });
      try {
        const response = await fetch(inlineUrl, {
          method: 'POST',
          body,
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
        });
        const type = response.headers.get('content-type') || '';
        if (!type.includes('application/json')) {
          throw new Error('پاسخ ورود یا اعتبارسنجی دریافت شد؛ نشست را بررسی کن. وضعیت ذخیره نامشخص است.');
        }
        const result = await response.json();
        if (!response.ok || !result.ok) {
          inlineNotice(result.message || 'ثبت انجام نشد؛ اطلاعات واردشده در فرم باقی مانده است.', 'error');
          return;
        }
        const changedWhileSaving = fingerprint !== JSON.stringify(
          Array.from(new FormData(form).entries()));
        const rows = new Map((result.rows || []).map(row => [row.key, row]));
        groups.filter(group => group.dataset.block === blockId).forEach(group => {
          const state = rows.get(group.dataset.key);
          if (state) inlineUpdateRow(group, state);
          if (!changedWhileSaving) delete group.dataset.unsavedEdit;
        });
        if (!result.deletable) lockSheetDelete(blockId);
        if (isDelivery) {
          // Close the modal only after the server confirms stock + wage commit.
          document.querySelectorAll('.prod131-dialog[open]').forEach(dialog => {
            if (dialog.id.startsWith('prod131-dialog-' + blockId + '-')) dialog.close();
          });
        }
        visibleRows(); // Update the existing KPI nodes, not the page.
        inlineNotice(result.message || 'ثبت با موفقیت انجام شد.', 'ok');
      } catch (error) {
        // Never retry an uncertain stock mutation automatically.
        inlineNotice(
          'پاسخ سرور دریافت نشد. وضعیت ثبت نامشخص است؛ قبل از ارسال دوباره، موجودی یا سوابق تحویل را بررسی کن. '
            + (error?.message || ''), 'error'
        );
      } finally {
        pendingInlineRequest = false;
        buttons.forEach(button => { button.disabled = false; });
      }
    });
  });

  visibleRows();
})();
