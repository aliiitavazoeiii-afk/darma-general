(function(){
  "use strict";
  var digits={"۰":"0","۱":"1","۲":"2","۳":"3","۴":"4","۵":"5","۶":"6","۷":"7","۸":"8","۹":"9","٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9"};
  function rawMoney(value){
    return String(value||"").replace(/[۰-۹٠-٩]/g,function(c){return digits[c]||c;}).replace(/[^0-9]/g,"");
  }
  function pretty(value){
    var raw=rawMoney(value);
    return raw ? Number(raw).toLocaleString("en-US").replace(/,/g,"٬") : "";
  }
  document.querySelectorAll(".money-input").forEach(function(input){
    input.value=pretty(input.value);
    input.addEventListener("input",function(){
      input.value=pretty(input.value);
      try{input.setSelectionRange(input.value.length,input.value.length);}catch(e){}
    });
    if(input.form){
      input.form.addEventListener("submit",function(){input.value=rawMoney(input.value);});
    }
  });
  document.querySelectorAll("[data-confirm]").forEach(function(btn){
    btn.addEventListener("click",function(e){
      if(!window.confirm(btn.getAttribute("data-confirm"))){e.preventDefault();}
    });
  });
})();
