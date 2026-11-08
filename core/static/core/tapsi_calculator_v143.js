/* V144 standalone Tapsi quotation. Read-only, no DB updates. */
(() => {
  "use strict";
  const root=document.getElementById("t143-calculator");
  const node=document.getElementById("t142-catalog");
  if(!root||!node)return;
  let catalog=[];
  try{catalog=JSON.parse(node.textContent||"[]");}catch(_){return;}
  const get=id=>document.getElementById("t143-"+id);
  const product=get("calc-product"),size=get("calc-size"),mode=get("calc-mode");
  const pack=get("calc-pack"),cost=get("calc-cost"),qty=get("calc-qty");
  const price=get("calc-price"),margin=get("calc-margin"),discount=get("calc-discount");
  const month=document.getElementById("t144-calc-monthly"),notice=get("calc-notice");
  const normalize=v=>String(v??"").replace(/[۰-۹]/g,c=>String(c.charCodeAt(0)-1776))
    .replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/[٬,\s]/g,"");
  const val=v=>Number(normalize(v))||0;
  const money=v=>new Intl.NumberFormat("fa-IR").format(Math.round(v));
  function breakdown(unit,units,cogs,promo,forecast){
    const gross=Math.round(unit*units);
    const commission=Math.round(gross*.15);
    const vat=Math.round(commission*.10);
    const insurance=Math.round(gross*.015);
    const projectedMonth=Math.max(gross,forecast);
    const monthlyBill=Math.min(2200000,Math.max(550000,Math.round(projectedMonth*.003)));
    const infrastructure=projectedMonth>0?Math.round(monthlyBill*gross/projectedMonth):monthlyBill;
    const extras=140000+promo;
    const net=gross-commission-vat-insurance-infrastructure-extras;
    const profit=net-cogs;
    return {gross,commission,vat,insurance,infrastructure,extras,net,profit,cogs,
      margin:gross?profit/gross*100:0,monthlyBill,projectedMonth};
  }
  function calculateTarget(target,units,cogs,promo,forecast){
    // Unlike a simple 0.3% flat charge, the monthly floor/cap produces
    // piecewise effective rates. Binary-search the exact rounded simulation.
    let lo=1,hi=1000;
    for(let i=0;i<60&&breakdown(hi,units,cogs,promo,forecast).margin<target;i++)hi*=2;
    if(breakdown(hi,units,cogs,promo,forecast).margin<target)return null;
    while(lo<hi){
      const mid=Math.floor((lo+hi)/2);
      if(breakdown(mid,units,cogs,promo,forecast).margin>=target)hi=mid;
      else lo=mid+1;
    }
    return lo;
  }
  const output=(name,value)=>{const e=document.getElementById("t144-result-"+name)||get("result-"+name);if(e)e.textContent=value;};
  function invalid(message){
    notice.textContent=message;
    root.querySelectorAll('[id^="t143-result-"],[id^="t144-result-"]').forEach(e=>e.textContent="—");
  }
  function render(){
    const count=val(qty.value),inside=val(pack.value),unitCost=val(cost.value);
    const promo=val(discount.value),forecast=val(month.value);
    const target=Number(String(margin.value).replace(",","."));
    if(count<1||count>10000||inside<1||inside>1000||unitCost<0||promo<0||forecast<0){
      invalid("تعداد و هزینه و فروش پیش‌بینی‌شده باید معتبر باشند.");return;
    }
    const cogs=count*inside*unitCost;
    let selling=val(price.value);
    if(mode.value==="margin"){
      if(!Number.isFinite(target)||target>=82||target< -100){invalid("درصد سود هدف باید کمتر از ۸۲٪ و حداقل منفی ۱۰۰٪ باشد.");return;}
      selling=calculateTarget(target,count,cogs,promo,forecast);
      if(selling===null){invalid("این درصد سود با این ورودی‌ها قابل محاسبه نیست.");return;}
      price.value=money(selling);
    }else if(selling<=0){invalid("قیمت هر پک باید مثبت باشد.");return;}
    const b=breakdown(selling,count,cogs,promo,forecast);
    for(const key of ["gross","cogs","commission","vat","insurance","infrastructure","extras","net","profit"])output(key,money(b[key]));
    output("margin",b.margin.toLocaleString("fa-IR",{maximumFractionDigits:2})+"٪");
    const profit=get("result-profit");
    profit.classList.toggle("text-danger",b.profit<0);profit.classList.toggle("text-success",b.profit>=0);
    notice.textContent="پیش‌بینی کل فروش ماه "+money(b.projectedMonth)+" تومان؛ زیرساخت کل ماه "+money(b.monthlyBill)+" تومان. سهم این سفارش متناسب با فروش آن از کل فروش پیش‌بینی‌شده لحاظ شده است؛ سهم نهایی با فروش واقعی ماه تغییر می‌کند.";
  }
  function selectProduct(){
    const p=catalog.find(v=>String(v.id)===product.value);
    size.replaceChildren();
    if(!p){size.disabled=true;render();return;}
    pack.value=p.pack_qty;
    for(const item of p.sizes){
      const opt=document.createElement("option");opt.value=item.id;opt.textContent=item.name+" · "+money(item.price)+" تومان";size.append(opt);
    }
    size.disabled=!p.sizes.length;selectSize();
  }
  function selectSize(){
    const p=catalog.find(v=>String(v.id)===product.value);
    const item=p?.sizes.find(v=>String(v.id)===size.value);
    if(item){cost.value=money(item.unit_cost);price.value=money(item.price);}
    render();
  }
  for(const p of catalog){const o=document.createElement("option");o.value=p.id;o.textContent=p.code+" · "+p.title+" ("+p.brand+")";product.append(o);}
  product.addEventListener("change",selectProduct);
  size.addEventListener("change",selectSize);
  mode.addEventListener("change",()=>{
    const reverse=mode.value==="margin";
    price.readOnly=reverse;margin.readOnly=!reverse;
    price.classList.toggle("t143-derived",reverse);
    margin.classList.toggle("t143-derived",!reverse);
    render();
  });
  for(const e of [pack,cost,qty,discount,price,margin,month])e.addEventListener("input",render);
  margin.readOnly=true;margin.classList.add("t143-derived");render();
})();
