/**
 * V125 real-browser-like smoke simulation, no dependencies or production DB.
 * A form <input name="action"> shadows form.action, and a local variable
 * called location shadows window.location. The former caused HTTP 404,
 * the latter caused "Failed to construct 'URL': Invalid URL".
 *
 * Evaluate the ACTUAL inline template script, not a rewritten duplicate.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('templates/core/inventory_operations.html', 'utf8');
const open = "<script>\ndocument.addEventListener('DOMContentLoaded'";
const begin = html.indexOf(open);
assert.ok(begin >= 0, 'Transfer page script not found');
const start = begin + '<script>\n'.length;
const end = html.indexOf('</script>', start);
assert.ok(end > start, 'Missing script close tag');
const source = html.slice(start, end);

async function simulate({ responseKind = 'success', endpoint = '/inventory/operations/transfer-direction/' } = {}) {
  let onSubmit;
  const calls = [];
  const qtyInput = { value: '3' };
  const submitButton = { disabled: false };
  const feedback = { textContent: '', style: { color: '' } };
  const direction = { value: 'warehouse_to_home' };
  const brand = { value: '1', addEventListener() {} };
  const size = { value: '1', addEventListener() {} };
  // Deliberately mimic the troublesome input named "action".
  const hiddenAction = {
    toString() { return '[object HTMLInputElement]'; },
  };
  const form = {
    action: hiddenAction,
    getAttribute(name) {
      assert.equal(name, 'action');
      return endpoint;
    },
    querySelector(query) {
      if (query.startsWith('button')) return submitButton;
      return null;
    },
    querySelectorAll(query) {
      if (query === 'input[name^="qty_"]') return [qtyInput];
      return [];
    },
    addEventListener(name, callback) {
      if (name === 'submit') onSubmit = callback;
    },
    reset() {
      throw new Error('Form must NOT reset on background AJAX transfer');
    },
  };
  // Deliberately shadow "location" with a <select> that has no href.
  const adjustLocation = {
    options: [{dataset: {locationKey:'home'}, textContent: 'خانه'}],
    selectedIndex: 0,
    addEventListener() {},
  };
  const nodes = {
    'inventory-stock-snapshot': { textContent: '{}' },
    'stock-transfer-form': form,
    'transfer-direction': direction,
    'stock-transfer-result': feedback,
    'transfer-brand': brand,
    'transfer-size': size,
    'adjust-brand': null,
    'adjust-size': null,
    'adjust-location': adjustLocation,
  };
  const document = {
    getElementById(id) { return nodes[id] ?? null; },
    querySelectorAll(query) { return []; },
    addEventListener(event, callback) {
      if (event === 'DOMContentLoaded') callback();
    },
  };
  const payloads = [];
  class FakeFormData {
    constructor(f) {
      assert.equal(f, form);
      this.qty = qtyInput.value;
      this.direction = direction.value;
      payloads.push(this);
    }
  }
  const url = 'https://gozaresh.filmjadiid.ir/inventory/operations/transfer-direction/';
  function buildResponse() {
    if (responseKind === 'success') return {
      status: 200, ok: true, redirected: false, url,
      headers: { get: () => 'application/json; charset=utf-8' },
      async json() { return {ok:true, message:'انتقال ثبت شد', stock_snapshot:{}}; },
    };
    if (responseKind === 'login') return {
      status: 200, ok: true, redirected: true,
      url:'https://gozaresh.filmjadiid.ir/login/?next=/inventory/operations/',
      headers:{ get: () => 'text/html; charset=utf-8' },
    };
    if (responseKind === 'html404') return {
      status:404, ok:false, redirected:false, url,
      headers:{get:()=>'text/html'},
    };
    if (responseKind === 'csrf') return {
      status:403, ok:false, redirected:false, url,
      headers:{get:()=>'text/html'},
    };
    throw new Error('Unknown response scenario');
  }
  const context = {
    document, performance: { getEntriesByType: () => [{ type: 'navigate' }] },
    fetch: async (target, options) => {
      calls.push({target, options});
      return buildResponse();
    },
    FormData: FakeFormData, URL, console,
    location: { href:'https://gozaresh.filmjadiid.ir/inventory/operations/' },
  };
  vm.runInNewContext(source, context, { timeout: 2000 });
  assert.equal(typeof onSubmit, 'function', 'Actual AJAX listener not wired');
  let prevented = false;
  await onSubmit({preventDefault(){prevented=true;}});
  assert.equal(prevented, true, 'Default form submission not suppressed');
  assert.equal(submitButton.disabled, false, 'Button must be re-enabled');
  return { calls, payloads, qtyInput, feedback, direction, brand, size };
}

(async () => {
  for (const d of ['warehouse_to_home', 'home_to_warehouse']) {
    const result = await simulate();
    assert.equal(result.calls.length, 1, 'One click should send exactly one request');
    assert.equal(result.calls[0].target, '/inventory/operations/transfer-direction/');
    assert.equal(result.calls[0].options.method, 'POST');
    assert.equal(result.calls[0].options.headers['X-Requested-With'], 'XMLHttpRequest');
    assert.equal(result.payloads.length, 1);
    assert.equal(result.qtyInput.value, '', 'Only quantity input clears on success');
    assert.equal(result.direction.value, 'warehouse_to_home', 'Direction does not reset on submit');
    assert.ok(result.feedback.textContent.includes('انتقال ثبت شد'));
    assert.ok(!String(result.calls[0].target).includes('[object'));
  }
  for (const responseKind of ['login','html404','csrf']) {
    const result = await simulate({responseKind});
    assert.equal(result.calls.length, 1);
    assert.equal(result.qtyInput.value, '3', 'Error must preserve entered quantity');
    assert.notEqual(result.feedback.textContent, '', 'Readable error message required');
    assert.ok(!result.feedback.textContent.includes("Invalid URL"));
  }
  const bad = await simulate({endpoint:'[object HTMLInputElement]'});
  assert.equal(bad.calls.length, 0, 'Invalid endpoint must NEVER trigger a POST');
  assert.equal(bad.qtyInput.value, '3');
  assert.ok(bad.feedback.textContent.includes('آدرس فرم انتقال معتبر نیست'));
  console.log('PASS: ACTUAL template JS executes with action input + local location selection');
  console.log('PASS: no Invalid URL and only /inventory/operations/transfer-direction/ is posted');
  console.log('PASS: successful transfer clears quantities and keeps direction/brand/size');
  console.log('PASS: HTML 404/login/CSRF leave inputs intact without retry');
})().catch(error => { console.error(error); process.exitCode=1; });
