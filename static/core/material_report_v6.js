(() => {
  const config = document.getElementById('materialReportConfig');
  const DOZEN_RATE = Number(config?.dataset.wageRate || 110000);

  const normalizeDigits = (value) => String(value ?? '')
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));

  const clean = (value) => {
    const raw = normalizeDigits(value).replace(/[٬\s]/g, '').replace(/,/g, '.');
    const parsed = Number(raw.replace(/[^0-9.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const fmt = (value) => String(Math.round(Number(value) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  const wageForPieces = (pieces) => (Math.max(0, pieces) * DOZEN_RATE) / 12;

  function installCompactCenteredGridStyle() {
    if (document.getElementById('materialReportV84Style')) return;
    const style = document.createElement('style');
    style.id = 'materialReportV84Style';
    style.textContent = `
      .excel-scroll{overflow-x:auto!important;direction:rtl!important}
      .material-grid{width:max-content!important;min-width:0!important;margin-right:0!important;margin-left:auto!important;table-layout:auto!important;direction:rtl!important;font-size:.84rem!important}
      .material-grid th,.material-grid td{padding:6px 8px!important;text-align:center!important;vertical-align:middle!important;white-space:nowrap}
      .material-grid .sticky-col{min-width:126px!important;width:126px!important;text-align:center!important}
      .material-grid .grid-input,.material-grid .form-select{min-width:108px!important;width:108px!important;max-width:108px!important;height:39px!important;padding:6px 8px!important;margin:0 auto!important;text-align:center!important;font-size:.84rem!important}
      .material-grid .form-select{text-align-last:center!important;padding-inline:6px 24px!important}
      .material-grid .select-cell{min-width:136px!important;width:136px!important}
      .material-grid .select-cell .form-select{min-width:126px!important;width:126px!important;max-width:126px!important}
      .material-grid input,.material-grid select{direction:ltr!important;text-align:center!important}
      .material-grid th{direction:rtl!important}
      .output-grid .output-status{text-align:center!important}
      .delivery-total-box{text-align:center!important}
      @media(max-width:575.98px){
        .material-grid{font-size:.9rem!important}
        .material-grid .grid-input,.material-grid .form-select{min-width:114px!important;width:114px!important;max-width:114px!important;height:42px!important;font-size:16px!important}
        .material-grid .select-cell,.material-grid .select-cell .form-select{min-width:132px!important;width:132px!important;max-width:132px!important}
      }
    `;
    document.head.appendChild(style);
  }

  function field(form, name) {
    const item = form.elements.namedItem(name);
    if (!item) return null;
    if (typeof RadioNodeList !== 'undefined' && item instanceof RadioNodeList) return item[0] || null;
    return item;
  }

  function read(form, name) {
    return field(form, name)?.value ?? '';
  }

  function write(form, name, value) {
    const node = field(form, name);
    if (node) node.value = value;
  }

  function parseCatalog(form) {
    try {
      return JSON.parse(form.querySelector('.material-cost-catalog')?.textContent || '{}');
    } catch (_error) {
      return {};
    }
  }

  function modelKeys(form) {
    return String(field(form, 'active_material_keys')?.value || '')
      .split(',')
      .map((key) => key.trim())
      .filter(Boolean);
  }

  function recalcModelCost(form, key, catalog) {
    const cut = Math.max(0, clean(read(form, 'in_' + key + '_cut')));
    const wageTotal = cut > 0 ? wageForPieces(cut) : 0;
    write(form, 'in_' + key + '_wage', wageTotal > 0 ? fmt(wageTotal) : '');

    const fabricKg = Math.max(0, clean(read(form, 'in_' + key + '_weight')));
    const delivered16 = Math.max(0, clean(read(form, 'in_' + key + '_elastic16')));
    const delivered25 = Math.max(0, clean(read(form, 'in_' + key + '_elastic25')));
    const remain16Raw = read(form, 'in_' + key + '_remain16');
    const remain25Raw = read(form, 'in_' + key + '_remain25');
    const used16Kg = Math.max(0, remain16Raw === '' ? delivered16 : delivered16 - Math.max(0, clean(remain16Raw)));
    const used25Kg = Math.max(0, remain25Raw === '' ? delivered25 : delivered25 - Math.max(0, clean(remain25Raw)));

    const e16Key = read(form, 'in_' + key + '_elastic16_key') || key;
    const e25Key = read(form, 'in_' + key + '_elastic25_key') || key;
    const fabricPricePerKg = Number(catalog?.fabric?.[key] || 0);
    const elastic16PricePerKg = Number(catalog?.elastic16?.[e16Key] || 0);
    const elastic25PricePerKg = Number(catalog?.elastic25?.[e25Key] || 0);

    const fabricBatchCost = fabricKg * fabricPricePerKg;
    const elasticBatchCost = (used16Kg * elastic16PricePerKg) + (used25Kg * elastic25PricePerKg);

    // V84 mirrors the server formula explicitly:
    // fabric/cut + tailor wage/cut + used elastic/cut.
    const fabricPerPiece = cut > 0 ? fabricBatchCost / cut : 0;
    const laborPerPiece = cut > 0 ? wageTotal / cut : 0;
    const elasticPerPiece = cut > 0 ? elasticBatchCost / cut : 0;
    const unitCost = fabricPerPiece + laborPerPiece + elasticPerPiece;

    write(form, 'in_' + key + '_cost', unitCost > 0 ? fmt(unitCost) : '');

    return {
      cut,
      totalCost: fabricBatchCost + wageTotal + elasticBatchCost,
    };
  }

  function recalcOutputRow(form, row) {
    let delivered = 0;
    row.querySelectorAll('input[name^="out_"]').forEach((input) => {
      delivered += Math.max(0, clean(input.value));
    });

    const totalCell = row.querySelector('.output-row-total');
    if (totalCell) totalCell.textContent = fmt(delivered);

    const key = row.dataset.cutSource || row.dataset.modelKey || '';
    const cut = Math.max(0, clean(read(form, 'in_' + key + '_cut')));
    const cutCell = row.querySelector('.output-cut-total');
    if (cutCell) cutCell.textContent = fmt(cut);

    const diff = delivered - cut;
    const diffCell = row.querySelector('.output-row-diff');
    if (diffCell) {
      diffCell.dataset.diff = String(diff);
      diffCell.classList.remove('shortage', 'surplus', 'exact');
      if (diff < 0) {
        diffCell.classList.add('shortage');
        diffCell.textContent = 'کسری ' + fmt(Math.abs(diff));
      } else if (diff > 0) {
        diffCell.classList.add('surplus');
        diffCell.textContent = 'مازاد ' + fmt(diff);
      } else {
        diffCell.classList.add('exact');
        diffCell.textContent = '۰';
      }
    }
    return delivered;
  }

  function recalcForm(form) {
    const catalog = parseCatalog(form);
    let totalCost = 0;
    let totalCut = 0;

    modelKeys(form).forEach((key) => {
      const result = recalcModelCost(form, key, catalog);
      if (result.cut > 0) {
        totalCut += result.cut;
        totalCost += result.totalCost;
      }
    });

    const avg = form.querySelector('.live-average-cost');
    if (avg) avg.textContent = fmt(totalCut > 0 ? totalCost / totalCut : 0);

    let delivered = 0;
    form.querySelectorAll('.output-data-row').forEach((row) => {
      delivered += recalcOutputRow(form, row);
    });

    const totalWage = field(form, 'delivery_wage');
    if (totalWage) {
      totalWage.value = delivered > 0 ? fmt(wageForPieces(delivered)) : '';
      totalWage.readOnly = true;
    }

    const grand = form.querySelector('.output-grand-total');
    if (grand) grand.textContent = fmt(delivered);
  }

  function bindForms() {
    document.querySelectorAll('.material-card form[data-block-id]').forEach((form) => {
      if (form.dataset.materialV77Bound === '1') return;
      form.dataset.materialV77Bound = '1';

      form.addEventListener('input', (event) => {
        if (event.target.matches(
          'input[name*="_weight"],input[name*="_elastic16"],input[name*="_elastic25"],input[name*="_remain16"],input[name*="_remain25"],input[name$="_cut"],input[name^="out_"]'
        )) {
          recalcForm(form);
        }
      });

      form.addEventListener('change', (event) => {
        if (event.target.matches('.material-source-select')) recalcForm(form);
      });
    });
  }

  function bindSearch() {
    const input = document.getElementById('materialBlockSearch');
    if (!input) return;
    const blocks = Array.from(document.querySelectorAll('.material-block'));
    input.addEventListener('input', () => {
      const query = normalizeDigits(input.value).trim().toLowerCase();
      blocks.forEach((block) => {
        const haystack = normalizeDigits(block.dataset.search || '').toLowerCase();
        block.classList.toggle('d-none', Boolean(query) && !haystack.includes(query));
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    installCompactCenteredGridStyle();
    bindForms();
    bindSearch();
  });
})();