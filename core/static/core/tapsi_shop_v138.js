/* V138 Tapsi: view-only cart preview; server computes all prices/fees and stock. */
(() => {
  "use strict";
  const root = document.getElementById("tapsi-shop");
  const catalogNode = document.getElementById("tapsi-shop-catalog");
  if (!root || !catalogNode) return;
  let catalog = [];
  try { catalog = JSON.parse(catalogNode.textContent) || []; } catch (_) { return; }
  const $ = id => document.getElementById(id);
  const query = $("tapsi-product-query");
  const suggestions = $("tapsi-product-results");
  const size = $("tapsi-product-size");
  const qty = $("tapsi-product-qty");
  const add = $("tapsi-add-item");
  const basket = $("tapsi-cart-body");
  const discount = $("tapsi-discount-cost");
  const save = $("tapsi-save-order");
  const selected = $("tapsi-selected-product");
  const nf = new Intl.NumberFormat("fa-IR");
  const normalize = value => String(value ?? "")
    .replace(/[ي]/g,"ی").replace(/[ك]/g,"ک")
    .replace(/[۰-۹]/g, c => "۰۱۲۳۴۵۶۷۸۹".indexOf(c))
    .replace(/[٠-٩]/g, c => "٠١٢٣٤٥٦٧٨٩".indexOf(c))
    .replace(/[\u200c\s]/g,"").toLowerCase();
  const numeric = value => {
    const x=Number(normalize(value).replace(/[,٬\s]/g,"").replace(/[^0-9-]/g,""));
    return Number.isFinite(x) ? Math.max(0,x) : 0;
  };
  const totalMoney=n => nf.format(Math.round(n || 0));
  const cart = new Map();
  let chosen = null;

  const refreshSelection = () => {
    const item = chosen?.sizes.find(x => String(x.id) === String(size.value));
    add.disabled = !item || !item.price || numeric(qty.value) < 1;
    if (chosen) {
      selected.textContent = chosen.brand + " · " + chosen.code + " · " + chosen.title
        + " · پک " + chosen.pack_qty + " تایی"
        + (item ? (item.price > 0
            ? " · سایز " + item.name + " · " + totalMoney(item.price) + " تومان"
            : " · برای این سایز هنوز قیمت فروش ثبت نشده است") : "");
    }
  };
  const choose = product => {
    chosen = product;
    query.value = product.code + " · " + product.title;
    suggestions.hidden = true;
    suggestions.replaceChildren();
    size.replaceChildren();
    product.sizes.forEach(entry => {
      const opt = document.createElement("option");
      opt.value = String(entry.id);
      // Keep all ACTIVE product sizes selectable so a missing channel price
      // never makes the whole size selector inaccessible.
      opt.disabled = false;
      opt.textContent = entry.name + (entry.price ? " · " + totalMoney(entry.price) + " تومان" : " · قیمت تعریف نشده");
      size.append(opt);
    });
    const first = product.sizes.find(x => x.price > 0) || product.sizes[0];
    if (first) size.value = String(first.id);
    size.disabled = !product.sizes.length;
    refreshSelection();
  };
  query?.addEventListener("input", () => {
    chosen = null;
    size.disabled = true;
    add.disabled = true;
    selected.textContent = "محصولی انتخاب نشده است.";
    size.replaceChildren();
    const q = normalize(query.value);
    suggestions.replaceChildren();
    if (!q) { suggestions.hidden = true; return; }
    const found = catalog.filter(p =>
      normalize(p.code).includes(q) || normalize(p.title).includes(q)
      || normalize(p.brand + " " + p.code + " " + p.title).includes(q)
    ).slice(0, 16);
    found.forEach(p => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = p.code + " · " + p.title + " (" + p.brand + "، پک " + p.pack_qty + ")";
      button.addEventListener("click", () => choose(p));
      suggestions.append(button);
    });
    if (!found.length) {
      const empty = document.createElement("p");
      empty.textContent = "کد یا عنوانی پیدا نشد؛ از بخش تعریف محصول، کد را اضافه کن.";
      suggestions.append(empty);
    }
    suggestions.hidden = false;
  });
  size?.addEventListener("change", refreshSelection);
  qty?.addEventListener("input", refreshSelection);

  const refreshCart = () => {
    basket.replaceChildren();
    let gross = 0;
    for (const item of cart.values()) {
      const tr = document.createElement("tr");
      const title = document.createElement("td");
      title.textContent = item.code + " · " + item.title + " / " + item.size;
      const amount = document.createElement("td");
      amount.textContent = totalMoney(item.quantity);
      amount.className = "tapsi-num";
      const unit = document.createElement("td");
      unit.textContent = totalMoney(item.price);
      unit.className = "tapsi-num";
      const total = document.createElement("td");
      const cost = item.price * item.quantity;
      gross += cost;
      total.textContent = totalMoney(cost);
      total.className = "tapsi-num";
      const remove = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button"; button.className="btn btn-sm btn-outline-danger";
      button.textContent = "×";
      button.setAttribute("aria-label","حذف قلم");
      button.addEventListener("click", () => {cart.delete(item.psId);refreshCart();});
      remove.append(button);
      const psId = document.createElement("input");
      psId.type="hidden"; psId.name="product_size_id"; psId.value=item.psId;
      const count = document.createElement("input");
      count.type="hidden";count.name="quantity";count.value=item.quantity;
      title.append(psId,count);
      tr.append(title,amount,unit,total,remove);
      basket.append(tr);
    }
    if (!cart.size) {
      const row=document.createElement("tr");const cell=document.createElement("td");
      cell.colSpan=5;cell.className="tapsi-empty";
      cell.textContent="ابتدا کد و سایز را انتخاب و به سفارش اضافه کن.";
      row.append(cell);basket.append(row);
    }
    save.disabled=cart.size===0;
    const commission=Math.round(gross*0.15);
    const discountCost=numeric(discount?.value);
    const shipping=cart.size ? 140000 : 0;
    $("tapsi-preview-gross").textContent=totalMoney(gross);
    $("tapsi-preview-fee").textContent=totalMoney(commission+shipping+discountCost);
    $("tapsi-preview-net").textContent=totalMoney(gross-commission-shipping-discountCost);
  };
  add?.addEventListener("click", () => {
    const selectedSize = chosen?.sizes.find(x => String(x.id) === String(size.value));
    const quantity=Math.trunc(numeric(qty.value));
    if (!chosen || !selectedSize || !selectedSize.price || quantity<1) return;
    const key=String(selectedSize.id);
    const old=cart.get(key);
    const newQuantity=quantity+(old?.quantity||0);
    if (newQuantity>10000) return;
    cart.set(key,{
      psId:key,quantity:newQuantity,price:selectedSize.price,
      code:chosen.code,title:chosen.title,size:selectedSize.name,
    });
    refreshCart();
  });
  discount?.addEventListener("input",refreshCart);
  refreshCart();
})();
