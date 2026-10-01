class V98PresentationMiddleware:
    """Inject a cache-busted UI helper into ERP HTML responses only.

    Business state, forms, routes and calculations are untouched. The helper is
    loaded with ?v=98 so browsers/service workers cannot keep the older cached
    sidebar/presentation behavior from V97.
    """

    SCRIPT = b'<script src="/static/core/number_format.js?v=98"></script>'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(response, "streaming", False):
            return response
        content_type = response.get("Content-Type", "")
        if response.status_code != 200 or "text/html" not in content_type:
            return response
        content = response.content
        # Limit the injection to pages using the ERP base helper; login/admin/static
        # responses are not modified.
        if b"core/number_format.js" not in content or self.SCRIPT in content:
            return response
        marker = b"</body>"
        if marker not in content:
            return response
        response.content = content.replace(marker, self.SCRIPT + marker, 1)
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
