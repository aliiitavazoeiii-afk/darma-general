// V126 regression: exercise the real inline transfer JavaScript in a tiny
// browser stand-in where local "location" is the ADJUSTMENT SELECT (no href).
// Old V125's new URL(transferForm.action,location.href) fails this test.
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
const file=fs.readFileSync('templates/core/inventory_operations.html','utf8');
const inline=file.split('<script>')[1]?.split('</script>')[0];
assert(inline,'transfer inline script missing');
assert(inline.includes('const location=document.getElementById(\'adjust-location\')'));
assert(!inline.includes('new URL(transferForm.action,location.href)'));
assert(inline.includes("const transferEndpoint=\"{% url 'inventory_transfer_direction_v123' %}\";"));
const script=inline.replace(
  `{% url 'inventory_transfer_direction_v123' %}`,
  '/inventory/operations/transfer-direction/'
);
let onSubmit;
const calls=[];
const submitButton={disabled:false};
const qtyInputs=[{value:'3'}];
const form={
  action:'/inventory/operations/transfer-direction/',
  fields:[],
  appendChild(node){this.fields.push(node)},
  querySelector(){return submitButton},
  querySelectorAll(selector){return selector.includes('qty_')?qtyInputs:[]},
  addEventListener(type,callback){if(type==='submit')onSubmit=callback},
};
const feedback={textContent:'',style:{}};
const elements={
  'inventory-stock-snapshot':{textContent:'{}'},
  'stock-transfer-form':form,
  'stock-transfer-result':feedback,
  // This element intentionally has no .href, as on the production page.
  'adjust-location':{
    options:[{dataset:{locationKey:'home'},textContent:'خانه'}],
    selectedIndex:0
  },
};
const document={
  getElementById(id){return elements[id]||null},
  querySelectorAll(){return []},
  createElement(){return {type:'',name:'',value:''}},
  addEventListener(type,cb){if(type==='DOMContentLoaded')cb()},
};
const endpoint='/inventory/operations/transfer-direction/';
async function fetch(url,options){
  calls.push({url,method:options.method});
  assert(typeof url==='string','request URL must be a safe relative string');
  assert(url.startsWith(endpoint),'request must target real transfer route');
  const result=options.method==='GET'?
    {ok:true,version:'v125',found:false}:
    {ok:true,version:'v125',message:'انتقال ثبت شد',stock_snapshot:{}};
  return {
    status:200,ok:true,redirected:false,type:'basic',
    headers:{get(name){return name.toLowerCase()==='content-type'?'application/json':null}},
    async json(){return result}
  };
}
const sandbox={
  document,fetch,FormData:class {constructor(formObject){assert(formObject===form)}},
  performance:{getEntriesByType(){return [{type:'navigate'}]}},
  window:{crypto:{randomUUID(){return '123e4567-e89b-42d3-a456-426614174000'}}},
  // The *actual* window.location may be fine. The local SELECT named location
  // previously shadowed it; no global location is supplied intentionally.
  console,URL,encodeURIComponent,setTimeout,clearTimeout,
};
vm.runInNewContext(script,sandbox,{filename:'inventory_operations.inline.js'});
assert.equal(typeof onSubmit,'function');
(async()=>{
  let prevented=false;
  await onSubmit({preventDefault(){prevented=true}});
  assert(prevented,'must never navigate/reload on transfer submit');
  assert.deepStrictEqual(calls,[
    {url:endpoint,method:'GET'},
    {url:endpoint,method:'POST'},
  ],'must GET-probe exactly the real route before POST, no URL constructor');
  assert.strictEqual(submitButton.disabled,false);
  assert.strictEqual(qtyInputs[0].value,'','only entered quantity cleared after success');
  assert(feedback.textContent.includes('ثبت شد'),'show confirmed success');
  console.log('PASS V126: no Invalid URL; GET route probe then POST; user selections persist');
})().catch(error=>{console.error(error);process.exitCode=1});
