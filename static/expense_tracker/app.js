(function(){
  "use strict";

  var digits={"۰":"0","۱":"1","۲":"2","۳":"3","۴":"4","۵":"5","۶":"6","۷":"7","۸":"8","۹":"9","٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9"};

  function rawMoney(value){
    return String(value||"")
      .replace(/[۰-۹٠-٩]/g,function(c){return digits[c]||c;})
      .replace(/[^0-9]/g,"");
  }

  function pretty(value){
    var raw=rawMoney(value);
    return raw ? Number(raw).toLocaleString("en-US").replace(/,/g,"٬") : "";
  }

  function escapeHtml(value){
    return String(value||"").replace(/[&<>"']/g,function(ch){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
    });
  }

  function formatNumber(value){
    return Number(value||0).toLocaleString("en-US").replace(/,/g,"٬");
  }

  function bindMoneyInputs(root){
    (root||document).querySelectorAll(".money-input").forEach(function(input){
      if(input.dataset.moneyReady) return;
      input.dataset.moneyReady="1";
      input.value=pretty(input.value);
      input.addEventListener("input",function(){
        input.value=pretty(input.value);
        try{input.setSelectionRange(input.value.length,input.value.length);}catch(e){}
      });
    });
  }

  function bindNormalMoneyForms(){
    document.querySelectorAll("form:not([data-ajax-expense])").forEach(function(form){
      if(form.dataset.moneySubmitReady) return;
      form.dataset.moneySubmitReady="1";
      form.addEventListener("submit",function(){
        form.querySelectorAll(".money-input").forEach(function(input){
          input.value=rawMoney(input.value);
        });
      });
    });
  }

  function setMetric(id,value){
    var el=document.getElementById(id);
    if(el) el.textContent=formatNumber(value);
  }

  function setSaveStatus(text,state){
    var box=document.getElementById("expense-save-status");
    if(!box) return;
    box.classList.remove("saving","success","error");
    if(state) box.classList.add(state);
    var label=box.querySelector("span:last-child");
    if(label) label.textContent=text;
  }

  function addRecentExpense(expense){
    var list=document.getElementById("recent-expense-list");
    if(!list || !expense) return;

    var empty=list.querySelector(".empty");
    if(empty) empty.remove();

    var row=document.createElement("div");
    row.className="transaction new-transaction";
    row.innerHTML=
      '<div class="transaction-icon accent-'+escapeHtml(expense.accent)+'">'+escapeHtml(expense.category.slice(0,1))+'</div>'+
      '<div class="transaction-main"><strong>'+escapeHtml(expense.title)+'</strong><small>'+escapeHtml(expense.category)+' · '+escapeHtml(expense.date)+'</small></div>'+
      '<div class="transaction-money"><strong class="money">−'+formatNumber(expense.amount)+'</strong><small>تومان</small></div>'+
      '<a class="icon-btn" href="/expenses/'+encodeURIComponent(expense.id)+'/edit/" aria-label="ویرایش">⋯</a>';

    list.insertBefore(row,list.firstChild);
    while(list.children.length>8){
      list.removeChild(list.lastElementChild);
    }
    window.setTimeout(function(){row.classList.remove("new-transaction");},900);
  }

  function bindExpenseAjax(){
    var form=document.querySelector("[data-ajax-expense]");
    if(!form || form.dataset.ajaxReady) return;
    form.dataset.ajaxReady="1";

    var submit=form.querySelector('button[type="submit"]');
    var amount=form.querySelector('[name="amount"]');
    var title=form.querySelector('[name="title"]');
    var note=form.querySelector('[name="note"]');
    var dateInput=form.querySelector('[name="date"]');
    var dateBadge=document.getElementById("entry-date-badge");

    if(dateInput && dateBadge){
      dateInput.addEventListener("change",function(){dateBadge.textContent=dateInput.value;});
    }

    form.addEventListener("submit",async function(e){
      e.preventDefault();

      var amountRaw=rawMoney(amount && amount.value);
      if(!amountRaw || Number(amountRaw)<=0){
        setSaveStatus("مبلغ هزینه را وارد کن","error");
        if(amount) amount.focus();
        return;
      }

      var selectedDate=dateInput ? dateInput.value : "";
      var selectedCategory=form.querySelector('[name="category"]:checked');

      var data=new FormData(form);
      data.set("amount",amountRaw);

      if(submit){
        submit.disabled=true;
        submit.dataset.oldText=submit.textContent;
        submit.textContent="در حال ثبت…";
      }
      setSaveStatus("در حال ذخیره خرج…","saving");

      try{
        var response=await fetch(form.action,{
          method:"POST",
          body:data,
          credentials:"same-origin",
          headers:{
            "X-Requested-With":"XMLHttpRequest",
            "Accept":"application/json"
          }
        });
        var payload=await response.json();
        if(!response.ok || !payload.ok){
          throw new Error(payload.message || "ثبت انجام نشد");
        }

        setMetric("mellat-balance",payload.mellat_balance);
        setMetric("today-total",payload.today_total);
        setMetric("week-total",payload.week_total);
        setMetric("month-total",payload.month_total);
        addRecentExpense(payload.expense);

        if(amount) amount.value="";
        if(title) title.value="";
        if(note) note.value="";
        if(dateInput) dateInput.value=selectedDate;
        if(selectedCategory) selectedCategory.checked=true;

        setSaveStatus("ثبت شد؛ تاریخ برای خرج بعدی همان ماند ✓","success");
        if(amount) amount.focus({preventScroll:true});
      }catch(err){
        setSaveStatus(err && err.message ? err.message : "ثبت خرج انجام نشد","error");
      }finally{
        if(submit){
          submit.disabled=false;
          submit.textContent=submit.dataset.oldText || "＋ ثبت خرج";
        }
      }
    });
  }

  function bindConfirmations(){
    document.querySelectorAll("[data-confirm]").forEach(function(btn){
      if(btn.dataset.confirmReady) return;
      btn.dataset.confirmReady="1";
      btn.addEventListener("click",function(e){
        if(!window.confirm(btn.getAttribute("data-confirm"))){e.preventDefault();}
      });
    });
  }

  function bindPwaInstall(){
    var installButtons=[
      document.getElementById("install-app-btn"),
      document.getElementById("install-app-btn-mobile")
    ].filter(Boolean);
    var deferredPrompt=null;

    function isStandalone(){
      return window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true;
    }

    function hideInstall(){
      installButtons.forEach(function(btn){btn.hidden=true;});
    }

    function showInstall(){
      if(isStandalone()) return hideInstall();
      installButtons.forEach(function(btn){btn.hidden=false;});
    }

    if("serviceWorker" in navigator && window.isSecureContext){
      window.addEventListener("load",function(){
        navigator.serviceWorker.register("/sw.js",{scope:"/"}).catch(function(){});
      });
    }

    window.addEventListener("beforeinstallprompt",function(event){
      event.preventDefault();
      deferredPrompt=event;
      showInstall();
    });

    installButtons.forEach(function(btn){
      btn.addEventListener("click",async function(){
        if(!deferredPrompt) return;
        deferredPrompt.prompt();
        try{await deferredPrompt.userChoice;}catch(e){}
        deferredPrompt=null;
        hideInstall();
      });
    });

    window.addEventListener("appinstalled",function(){
      deferredPrompt=null;
      hideInstall();
    });

    if(isStandalone()) hideInstall();
  }

  bindMoneyInputs(document);
  bindNormalMoneyForms();
  bindExpenseAjax();
  bindConfirmations();
  bindPwaInstall();
})();
