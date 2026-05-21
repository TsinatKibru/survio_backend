"""
Custom security middleware for Survio.

Injects a Content-Security-Policy header without requiring the django-csp
package. Only active in production (settings.py adds this to MIDDLEWARE only
when DEBUG=False).
"""


class SecurityHeadersMiddleware:
    """
    Adds Content-Security-Policy and Permissions-Policy headers to every
    response. Fixes the OpenVAS finding: "CSP Header Not Set".
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # ── Content-Security-Policy ───────────────────────────────────────────
        # 'unsafe-inline' is required for Django admin's inline scripts/styles.
        csp_directives = "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",   # admin needs eval for date widgets
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com",
            "font-src 'self' fonts.gstatic.com data:",
            "img-src 'self' data: alexpsycht.pythonanywhere.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ])
        response["Content-Security-Policy"] = csp_directives

        # ── Permissions-Policy (bonus hardening) ─────────────────────────────
        response["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        return response
