/* V142: DOM-only basket preview. Posting, prices and inventory remain server authoritative. */
(() => {
  "use strict";
  const catalogNode = document.getElementById("t142-catalog");
  const form = document.getElementById("t142-order-form");
  if (!catalogNode || !form) return;
  let catalog = [];
  try { catalog = JSON.parse(catalogNode.textContent || "[]"); } catch (_) { return; }
  const el = id => document.getElementById(id);
  const query = el("t142-query"), suggestions = el("t142-suggestions");
  const size = el("t142-size"), qty = el("t142-qty"), add = el("t142-add");
  const selected = el("t142-selected"), lines = el("t142-lines");
  const discount = el("t142-discount"), save = el("t142-save");
  const basket = new Map();
  let chosen = null;
  const nf = new Intl.NumberFormat("fa-IR");
  const digits = v => String(v ?? "").replace(/[۰-۹]/g, c => String(c.charCodeAt(0)-1776))
    .replace(/[٠-٩]/g, c => String(c.charCodeAt(0)-1632)).replace(/[٬,\s]/g, "");
  const amount = v => Math.max(0, Number(digits(v)) || 0);
  const money = v => nf.format(Math.round(v || 0));
  function viewSelection(){
    const variant = chosen?.sizes.find(v => String(v.id) === String(size.value));
    const count = amount(qty.value);
    add.disabled = !(variant && variant.price > 0 && count >= 1 && count <= 10000);
    selected.textContent = !chosen ? "هنوز محصولی انتخاب نشده است."
      : chosen.code + " · " + chosen.title + (variant
      ? " · سایز " + variant.name + (variant.price > 0
        ? " · " + money(variant.price) + " تومان"
        : " · این سایز قیمت معتبر ندارد؛ از قیمت‌گذاری اصلاح کن.")
      : "");
  }
  function pick(product){
    chosen = product; query.value = product.code + " · " + product.title;
    suggestions.hidden = true;
    size.replaceChildren();
    for (const variant of product.sizes) {
      const option = document.createElement("option");
      option.value = variant.id;
      option.textContent = variant.name + " · " + (variant.price > 0
        ? money(variant.price) + " تومان" : "قیمت ثبت نشده");
      size.appendChild(option);
    }
    size.disabled = !product.sizes.length;
    const first = product.sizes.find(v => v.price > 0) || product.sizes[0];
    if (first) size.value = String(first.id);
    viewSelection();
  }
  function search(){
    const q = query.value.trim().toLocaleLowerCase("fa-IR");
    chosen = null; add.disabled = true; size.disabled = true;
    size.replaceChildren(); suggestions.replaceChildren();
    if (!q) { suggestions.hidden = true; viewSelection(); return; }
    const matches = catalog.filter(p => (p.code + " " + p.title + " " + p.brand)
      .toLocaleLowerCase("fa-IR").includes(q)).slice(0,12);
    if (!matches.length) {
      const p = document.createElement("p"); p.textContent="کالایی با این کد یا عنوان پیدا نشد.";
      suggestions.append(p);
    }
    for(const product of matches){
      const b = document.createElement("button");
      b.type="button";
      b.textContent=product.code + " · " + product.title;
      const sub=document.createElement("span");sub.className="t142-result-sub";
      sub.textContent=product.brand + " · " + product.pack_qty + " عددی";
      b.append(sub);b.addEventListener("click",()=>pick(product));suggestions.append(b);
    }
    suggestions.hidden=false;viewSelection();
  }
  query.addEventListener("input",search);
  query.addEventListener("focus",()=>{if(query.value.trim()&&!chosen)search();});
  document.addEventListener("click",event=>{if(!event.target.closest(".t142-searchbox"))suggestions.hidden=true;});
  size.addEventListener("change",viewSelection);qty.addEventListener("input",viewSelection);
  function value(label, textValue) {
    const node=document.createElement("div");node.className="t142-line-value";
    const small=document.createElement("small");small.textContent=label;
    const strong=document.createElement("strong");strong.className="money";strong.textContent=textValue;
    node.append(small,strong);return node;
  }
  function render(){
    lines.replaceChildren();
    let gross=0, count=0, cogs=0;
    for(const item of basket.values()){
      gross += item.price * item.quantity;count+=item.quantity;
      cogs += (item.unit_cost || 0) * item.pack_qty * item.quantity;
      const row=document.createElement("div");row.className="t142-line";
      const title=document.createElement("div");title.className="t142-line-title";
      const name=document.createElement("strong");name.textContent=item.code+" · "+item.title;
      const sub=document.createElement("small");sub.textContent="سایز "+item.size;
      title.append(name,sub);
      const del=document.createElement("button");del.type="button";del.className="t142-remove";del.textContent="×";
      del.setAttribute("aria-label","حذف "+item.code+" سایز "+item.size);
      del.addEventListener("click",()=>{basket.delete(item.id);render();});
      const id=document.createElement("input");id.type="hidden";id.name="product_size_id";id.value=item.id;
      const quantity=document.createElement("input");quantity.type="hidden";quantity.name="quantity";quantity.value=item.quantity;
      row.append(title,value("تعداد پک",money(item.quantity)),
        value("فی فروش",money(item.price)),value("جمع",money(item.price*item.quantity)),del,id,quantity);
      lines.append(row);
    }
    if(!basket.size){
      const empty=document.createElement("div");empty.className="t142-empty";
      empty.textContent="کالایی به این سفارش اضافه نشده است.";lines.append(empty);
    }
    el("t142-line-count").textContent=money(basket.size)+" قلم · "+money(count)+" پک";
    const commission=Math.round(gross*0.15);
    const vat=Math.round(commission*0.10);
    const insurance=Math.round(gross*0.015);
    const extras=(basket.size?140000:0)+amount(discount.value);
    const fee=commission+vat+insurance+extras;
    el("t144-entry-insurance").textContent=money(insurance);
    el("t144-entry-infrastructure").textContent=basket.size?"در گزارش ماه":"—";
    el("t143-entry-commission").textContent=money(commission);
    el("t143-entry-vat").textContent=money(vat);
    el("t143-entry-extras").textContent=money(extras);
    el("t143-entry-cogs").textContent=money(cogs);
    el("t143-entry-profit").textContent=basket.size?money(gross-fee-cogs)+" (قبل از زیرساخت)":"۰";
    el("t142-gross").textContent=money(gross);
    el("t142-fees").textContent=money(fee);
    el("t142-net").textContent=money(gross-fee);
    save.disabled=!basket.size;
  }
  add.addEventListener("click",()=>{
    const variant=chosen?.sizes.find(v=>String(v.id)===String(size.value));
    const count=amount(qty.value);
    if(!chosen||!variant||variant.price<=0||count<1||count>10000) return;
    const id=String(variant.id), previous=basket.get(id);
    basket.set(id,{id,code:chosen.code,title:chosen.title,size:variant.name,
      price:variant.price,unit_cost:variant.unit_cost||0,pack_qty:chosen.pack_qty,quantity:(previous?.quantity||0)+count});
    render();qty.value="1";viewSelection();query.focus();
  });
  discount.addEventListener("input",render);
  form.addEventListener("submit",()=>{
    if(!basket.size)return;
    save.disabled=true;save.textContent="در حال ثبت سفارش...";
  });
  render();
})();
