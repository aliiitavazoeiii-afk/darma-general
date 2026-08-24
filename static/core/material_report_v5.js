(() => {
  const config = document.getElementById('materialReportConfig');
  const DOZEN_RATE = Number(config?.dataset.wageRate || 110000);
  const clean = (v) => Number(String(v ?? '').replace(/[٬,\s]/g, '').replace(/[^0-9.-]/g, '')) || 0;
  const fmt = (v) => String(Math.round(v || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  const wageForPieces = (pieces) => (Math.max(0, pieces) * DOZEN_RATE) / 12;

  function recalcForm(form) {
    form.querySelectorAll('input[name$="_cut"]').forEach((cut) => {
      const wageName = cut.name.replace(/_cut$/, '_wage');
      const wage = form.querySelector(`input[name="${wageName}"]`);
      if (wage) {
        wage.value = clean(cut.value) > 0 ? fmt(wageForPieces(clean(cut.value))) : '';
        wage.readOnly = true;
      }
    });
    let delivered = 0;
    form.querySelectorAll('input[name^="out_"]').forEach((input) => { delivered += Math.max(0, clean(input.value)); });
    const totalWage = form.querySelector('input[name="delivery_wage"]');
    if (totalWage) {
      totalWage.value = delivered > 0 ? fmt(wageForPieces(delivered)) : '';
      totalWage.readOnly = true;
    }
  }

  function bind() {
    document.querySelectorAll('.material-card form').forEach((form) => {
      if (form.dataset.wageBound === '1') return;
      form.dataset.wageBound = '1';
      form.addEventListener('input', (e) => {
        if (e.target.matches('input[name$="_cut"],input[name^="out_"]')) recalcForm(form);
      });
      recalcForm(form);
    });
  }
  document.addEventListener('DOMContentLoaded', bind);
})();
