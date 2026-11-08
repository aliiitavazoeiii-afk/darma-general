/* V143 isolated Tapsi calculator. No network or server mutations. */
(() => {
  "use strict";
  const root = document.getElementById("t143-calculator");
  const data = document.getElementById("t142-catalog");
  if (!root || !data) return;
  let catalog;
  try { catalog=JSON.parse(data.textContent || "[]"); } catch (_) { return; }
  const byId = id => document.getElementById("t143-" + id);
  const product = byId("calc-product"), size = byId("calc-size");
  const mode=byId("calc-mode"), pack=byId("calc-pack"),cost=byId("calc-cost");
  const qty=byId("calc-qty"),discount=byId("calc-discount");
  const price=byId("calc-price"),margin=byId("calc-margin");
  const notice=byId("calc-notice");
  const digits = v=>String(v??"").replace(/[۰-۹]/g,c=>String(c.charCodeAt(0)-1776))
    .replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/[٬,\s]/g,"");
  const number = v=>Number(digits(v))||0;
  const format = v=>new Intl.NumberFormat("fa-IR").format(Math.round(v));
  function calc(salePrice, count, costOfGoods, promotion){
    const gross=salePrice*count;
    const commission=Math.round(gross*.15);
    const vat=Math.round(commission*.10);
    const extras=140000+promotion;
    const fee=commission+vat+extras;
    const profit=gross-costOfGoods-fee;
    return {gross,commission,vat,extras,fee,profit,
      net:gross-fee,margin:gross>0?100*profit/gross:0};
  }
  function calculateTarget(target,count,cogs,promotion){
    const t=target/100;
    const denominator=1-.15*1.10-t;
    if(denominator<=0||!Number.isFinite(denominator))return null;
    let unit=Math.max(1,Math.ceil((cogs+140000+promotion)/denominator/count));
    for(let i=0;i<64;i++){
      if(calc(unit,count,cogs,promotion).margin + 1e-10>=target)return unit;
      unit++;
    }
    return unit;
  }
  function clearOutput(error){
    notice.textContent=error;
    root.querySelectorAll('[id^="t143-result-"]').forEach(e=>e.textContent="—");
  }
  function show(){
    const count=number(qty.value), unitCost=number(cost.value), packQty=number(pack.value);
    const promotion=number(discount.value);
    const target=Number(String(margin.value).replace(",","."));
    const valid=count>=1&&count<=10000&&packQty>=1&&packQty<=1000
      &&unitCost>=0&&promotion>=0;
    if(!valid){clearOutput("مقادیر تعداد، بهای کالا و تخفیف باید معتبر و غیرمنفی باشند.");return;}
    const cogs=unitCost*packQty*count;
    let unitPrice=number(price.value);
    if(mode.value==="margin"){
      if(!Number.isFinite(target)||target>=83.5||target < -100){
        clearOutput("درصد سود هدف باید کمتر از ۸۳٫۵٪ باشد؛ هزینه‌های متغیر تپسی به‌تنهایی ۱۶٫۵٪ فروش هستند.");
        return;
      }
      unitPrice=calculateTarget(target,count,cogs,promotion);
      if(unitPrice===null){clearOutput("برای این درصد سود، قیمت قابل محاسبه نیست.");return;}
      price.value=format(unitPrice);
    }else if(unitPrice<=0){
      clearOutput("قیمت فروش هر پک باید بیشتر از صفر باشد.");return;
    }
    const m=calc(unitPrice,count,cogs,promotion);
    for(const [key,value] of Object.entries({gross:m.gross,cogs,commission:m.commission,
      vat:m.vat,extras:m.extras,net:m.net,profit:m.profit})){
      byId("result-"+key).textContent=format(value);
    }
    byId("result-margin").textContent=m.margin.toLocaleString("fa-IR",{maximumFractionDigits:2})+"٪";
    byId("result-profit").classList.toggle("text-danger",m.profit<0);
    byId("result-profit").classList.toggle("text-success",m.profit>=0);
    notice.textContent=mode.value==="margin"
      ? "قیمت پیشنهادی هر پک برای رسیدن به حاشیه سود هدف، با تمام هزینه‌های همین سفارش محاسبه شد."
      : "درصد سود واقعی = سود خالص تقسیم بر فروش کل؛ این پیش‌نمایش هیچ قیمتی را ذخیره نمی‌کند.";
  }
  function chooseProduct(){
    const selected=catalog.find(p=>String(p.id)===product.value);
    size.replaceChildren();
    if(!selected){
      size.disabled=true;show();return;
    }
    pack.value=selected.pack_qty;
    for(const variant of selected.sizes){
      const option=document.createElement("option");option.value=variant.id;
      option.textContent=variant.name+" · "+format(variant.price)+" تومان";size.append(option);
    }
    size.disabled=!selected.sizes.length;
    chooseSize();
  }
  function chooseSize(){
    const selected=catalog.find(p=>String(p.id)===product.value);
    const variant=selected?.sizes.find(s=>String(s.id)===size.value);
    if(variant){
      cost.value=format(variant.unit_cost);
      price.value=format(variant.price);
    }
    show();
  }
  for(const p of catalog){
    const option=document.createElement("option");
    option.value=p.id;option.textContent=p.code+" · "+p.title+" ("+p.brand+")";
    product.append(option);
  }
  product.addEventListener("change",chooseProduct);
  size.addEventListener("change",chooseSize);
  mode.addEventListener("change",()=>{
    const reverse=mode.value==="margin";
    price.readOnly=reverse;
    margin.readOnly=!reverse;
    price.classList.toggle("t143-derived",reverse);
    margin.classList.toggle("t143-derived",!reverse);
    show();
  });
  for(const field of [pack,cost,qty,discount,price,margin])field.addEventListener("input",show);
  margin.readOnly=true;
  margin.classList.add("t143-derived");
  show();
})();
