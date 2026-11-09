/* V145 independent single-pack quotation: no product lookup, no monthly floor/cap. */
(() => {
  "use strict";
  const container = document.getElementById("t143-calculator");
  if (!container) return;
  const get = id => document.getElementById(id);
  const mode = get("t143-calc-mode");
  const cost = get("t145-calc-cost"), price = get("t145-calc-price");
  const target = get("t145-calc-target"), discount = get("t145-calc-discount");
  const priceWrap = get("t145-price-wrap"), marginWrap = get("t145-margin-wrap");
  const message = get("t145-calc-message");
  const format = value => new Intl.NumberFormat("fa-IR").format(value);
  const normalize = value => String(value ?? "").replace(/[۰-۹]/g, c => String(c.charCodeAt(0)-1776))
    .replace(/[٠-٩]/g, c => String(c.charCodeAt(0)-1632)).replace(/[٬,\s]/g, "");
  function nonnegative(input) {
    const raw = normalize(input);
    if (!/^\d+$/.test(raw)) return null;
    const parsed = Number(raw);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
  }
  function breakdown(sale, cogs, reduction) {
    // Same half-up rounding as Python Decimal money() for positive toman amounts.
    const commission = Math.round(sale * .15);
    const vat = Math.round(commission * .10);
    const insurance = Math.round(sale * .015);
    const infrastructure = Math.round(sale * .003);
    const shipping = 140000; // one order, even if its product is a multipack
    const discountFee = Math.round(reduction * .10);
    const fees = commission + vat + insurance + infrastructure + shipping + discountFee;
    const net = sale - fees;
    const profit = net - cogs;
    return {
      price: sale, cost: cogs, commission, vat, insurance, infrastructure,
      shipping, discount: discountFee, fees, net, profit,
      margin: sale > 0 ? (profit / sale) * 100 : 0,
    };
  }
  function targetPrice(desired, cogs, reduction) {
    // Maximum achievable margin tends toward 81.7% because variable fees are 18.3%.
    if (!Number.isFinite(desired) || desired >= 81.7 || desired < -100) return null;
    const sufficient = candidate => breakdown(candidate, cogs, reduction).margin >= desired;
    let hi = 1000;
    for (let step = 0; step < 52 && !sufficient(hi); step++) hi *= 2;
    if (!Number.isSafeInteger(hi) || !sufficient(hi)) return null;
    let lo = 1;
    while (lo < hi) {
      const mid = Math.floor((hi + lo) / 2);
      if (sufficient(mid)) hi = mid;
      else lo = mid + 1;
    }
    return lo;
  }
  function clearResults(error) {
    message.textContent = error;
    container.querySelectorAll('[id^="t145-result-"]').forEach(e => e.textContent = "—");
  }
  function show() {
    const cogs = nonnegative(cost.value), reduction = nonnegative(discount.value);
    if (cogs === null || reduction === null) {
      clearResults("بهای تمام‌شده و تخفیف باید عدد صحیح و غیرمنفی باشند."); return;
    }
    let sale;
    if (mode.value === "margin") {
      const desired = Number(String(target.value).replace(",", "."));
      if (!target.value.trim() || !Number.isFinite(desired) || desired >= 81.7 || desired < -100) {
        clearResults("درصد سود هدف باید کمتر از ۸۱٫۷٪ و حداقل منفی ۱۰۰٪ باشد."); return;
      }
      sale = targetPrice(desired, cogs, reduction);
      if (sale === null) { clearResults("قیمت قابل محاسبه نیست؛ درصد سود را کاهش بده."); return; }
    } else {
      sale = nonnegative(price.value);
      if (sale === null || sale <= 0) {
        clearResults("قیمت فروش باید عدد صحیح مثبت باشد."); return;
      }
    }
    const results = breakdown(sale, cogs, reduction);
    for (const [key, value] of Object.entries(results)) {
      const node = get("t145-result-" + key);
      if (node) node.textContent = key === "margin"
        ? value.toLocaleString("fa-IR", { maximumFractionDigits: 2 }) + "٪"
        : format(value);
    }
    const profitNode = get("t145-result-profit");
    profitNode.classList.toggle("text-danger", results.profit < 0);
    profitNode.classList.toggle("text-success", results.profit >= 0);
    message.textContent = mode.value === "margin"
      ? "حداقل قیمت فروش برای رسیدن به درصد سود هدف، با ریز هزینه‌های مستقل محاسبه شد."
      : "سود خالص و درصد سود بر اساس قیمت فروش و بهای تمام‌شده کل پک محاسبه شدند.";
  }
  mode.addEventListener("change", () => {
    const fromMargin = mode.value === "margin";
    priceWrap.hidden = fromMargin;
    marginWrap.hidden = !fromMargin;
    show();
  });
  for (const node of [cost, price, target, discount]) node.addEventListener("input", show);
  show();
})();
