import re


class V98PresentationMiddleware:
    """Presentation-only V101 finance submenu helper.

    Keep the original Finance & Tools expandable submenu and add one server-side
    Accounts entry that points to the existing finance_accounts view. No model,
    accounting, inventory, payment, receipt, or calculation logic is changed.
    """

    SCRIPT = '<script src="/static/core/number_format.js?v=101"></script>'
    FINANCE_GROUP_RE = re.compile(
        r'(<section class="erp-nav-group)([^\"]*)(">\s*'
        r'<button class="erp-nav-group-toggle"[^>]*>.*?'
        r'<span class="erp-nav-group-title">\s*مالی و ابزار\s*</span>.*?'
        r'</button>\s*<div class="erp-nav-group-items">)(.*?)(</div>\s*</section>)',
        re.DOTALL,
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def _finance_group(self, match, path):
        prefix, classes, head, items, tail = match.groups()
        if path.startswith("/finance/accounts/"):
            if "current" not in classes:
                classes += " current"
            if "open" not in classes:
                classes += " open"

        if 'href="/finance/accounts/"' not in items:
            active = "active" if path.startswith("/finance/accounts/") else ""
            account_link = (
                f'<a data-finance-accounts-nav="v101" class="{active}" '
                'href="/finance/accounts/"><span class="erp-dot"></span>حساب‌ها</a>\n'
            )
            calc_match = re.search(r'<a[^>]+href="/calculator/"', items)
            if calc_match:
                items = items[:calc_match.start()] + account_link + items[calc_match.start():]
            else:
                items = items + account_link

        return prefix + classes + head + items + tail

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(response, "streaming", False):
            return response
        content_type = response.get("Content-Type", "")
        if response.status_code != 200 or "text/html" not in content_type:
            return response

        content = response.content.decode("utf-8", errors="replace")
        if "core/number_format.js" not in content:
            return response

        path = getattr(request, "path", "") or ""
        content, matched = self.FINANCE_GROUP_RE.subn(
            lambda m: self._finance_group(m, path), content, count=1
        )

        if self.SCRIPT not in content and "</body>" in content:
            content = content.replace("</body>", self.SCRIPT + "</body>", 1)

        response.content = content.encode("utf-8")
        response["X-Darma-Finance-Accounts-V101"] = "present" if matched else "not-found"
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
