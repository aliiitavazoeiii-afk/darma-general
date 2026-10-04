class V98PresentationMiddleware:
    """Presentation-only helper.

    V103 keeps Finance & Tools navigation in base.html as one direct /finance/
    entry. This middleware no longer rewrites the finance navigation; it only
    injects a cache-busted UI helper script into HTML responses.
    """

    SCRIPT = '<script src="/static/core/number_format.js?v=103"></script>'

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
        if "core/number_format.js" not in content:
            return response

        if self.SCRIPT not in content and "</body>" in content:
            content = content.replace("</body>", self.SCRIPT + "</body>", 1)

        response.content = content.encode("utf-8")
        response["X-Darma-Finance-Nav-V103"] = "direct"
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
