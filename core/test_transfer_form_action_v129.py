"""V129 regression: HTML input[name=action] must not override form.action URL.

Production evidence:
 POST /inventory/operations/[object%20HTMLInputElement] -> HTTP 404
This class tests both the source guard and, on CI Node, JavaScript expression
evaluation with a mocked name-shadowed form. No DB or stock writes.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

from django.conf import settings
from django.test import SimpleTestCase


class TransferFormActionShadowV129Tests(SimpleTestCase):
    @staticmethod
    def _source():
        return (
            Path(settings.BASE_DIR) / "templates/core/inventory_operations.html"
        ).read_text(encoding="utf-8")

    def test_hidden_action_input_cannot_shadow_fetch_url(self):
        html = self._source()
        self.assertIn('name="action" value="transfer"', html)
        self.assertIn('action="{% url \'inventory_operations\' %}"', html)
        self.assertIn("await fetch(transferForm.getAttribute('action'),{", html)
        self.assertNotIn("fetch(transferForm.action,", html)
        self.assertIn("body:new FormData(transferForm)", html)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_actual_js_expression_with_name_shadowed_form(self):
        program = r"""
const fs = require('node:fs');
const text = fs.readFileSync('templates/core/inventory_operations.html', 'utf8');
const match = text.match(/await fetch\((transferForm[^,]+),\{/);
if (!match) throw new Error('Cannot find production fetch target expression');
// Real HTMLFormElement.action may resolve to a child input named 'action'.
// Emulate that browser DOM name/property collision intentionally.
const hiddenInput = {toString() {return '[object HTMLInputElement]'}};
const transferForm = {
  action: hiddenInput,
  getAttribute(name) {
    if (name !== 'action') throw Error('unexpected attribute');
    return '/inventory/operations/';
  },
};
const target = Function('transferForm', 'return ' + match[1])(transferForm);
if (target !== '/inventory/operations/') throw Error('POST would be sent to ' + target);
console.log('SUCCESS: browser-style action property shadowing does not affect fetch URL');
"""
        proc = subprocess.run(
            ["node", "-e", program], cwd=settings.BASE_DIR,
            text=True, capture_output=True, check=False, timeout=12,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
