import re


class V98PresentationMiddleware:
    """V99 server-rendered finance navigation + cache-busted presentation helper.

    This middleware is presentation-only. It does not touch models, forms,
    accounting logic, inventory logic, or routes. The Finance & Tools sidebar
    entry is rewritten on the SERVER before HTML reaches the browser so the
    result no longer depends on JavaScript selectors or browser cache.
    """

    SCRIPT = '<script src="/static/core/number_format.js?v=99"></script>'
    FINANCE_GROUP_RE = re.compile(
        r'<section class="erp-nav-group[^\"]*">\s*'
        r'<button class="erp-nav-group-toggle"[^>]*>.*?'
        r'<span class="erp-nav-group-title">\s*مالی و ابزار\s*</span>.*?'
        r'</button>\s*'
        r'<div class="erp-nav-group-items">.*?</div>\s*'
        r'</section>',
        re.DOTALL,
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(response, "streaming", False):
            return response
        content_type = response.get("Content-Type", "")
        if response.status_code != 200 or "text/html" not in content_type:
            return response

        content = response.content.decode("utf-8", errors="replace")
        # Limit all presentation changes to ERP pages using the shared helper.
        if "core/number_format.js" not in content:
            return response

        path = getattr(request, "path", "") or ""
        active = "active" if (
            path.startswith("/finance/")
            or path.startswith("/payments/")
            or path.startswith("/calculator/")
        ) else ""
        finance_link = (
            f'<a data-finance-root-nav="server-v99" class="{active}" href="/finance/">'
            '<span class="erp-dot"></span>مالی و ابزار</a>'
        )

        # Replace the actual hard-coded submenu emitted by base.html. This is the
        # canonical V99 fix and happens before the browser/JS sees the document.
        content, replaced = self.FINANCE_GROUP_RE.subn(finance_link, content, count=1)

        # Always inject the cache-busted V99 helper as well; it handles global
        # underline removal + slightly larger raw-material KPI numbers.
        if self.SCRIPT not in content and "</body>" in content:
            content = content.replace("</body>", self.SCRIPT + "</body>", 1)

        response.content = content.encode("utf-8")
        response["X-Darma-Finance-Nav-V99"] = "server" if replaced else "not-found"
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
