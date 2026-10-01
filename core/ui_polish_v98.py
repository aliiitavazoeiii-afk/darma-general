import re


class V98PresentationMiddleware:
    """Server-rendered finance navigation + cache-busted presentation helper.

    Presentation-only: no models, forms, accounting logic, inventory logic, or
    routes are mutated. V102 also disables HTML caching so the browser cannot
    keep an older Finance hub after deployment.
    """

    SCRIPT = '<script src="/static/core/number_format.js?v=102"></script>'
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
            f'<a data-finance-root-nav="server-v102" class="{active}" href="/finance/">'
            '<span class="erp-dot"></span>مالی و ابزار</a>'
        )

        content, replaced = self.FINANCE_GROUP_RE.subn(finance_link, content, count=1)

        if self.SCRIPT not in content and "</body>" in content:
            content = content.replace("</body>", self.SCRIPT + "</body>", 1)

        response.content = content.encode("utf-8")
        response["X-Darma-Finance-Nav-V102"] = "server" if replaced else "not-found"
        # V102: force fresh ERP HTML after deploy. Static assets still have their
        # own cache policy; this only prevents stale rendered pages/navigation.
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
