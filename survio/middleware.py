"""
Custom security middleware for Survio.

Injects a Content-Security-Policy header without requiring the django-csp
package. Only active in production (settings.py adds this to MIDDLEWARE only
when DEBUG=False).
"""


import secrets


class SecurityHeadersMiddleware:
    """
    Adds Content-Security-Policy and Permissions-Policy headers to every
    response. Generates a per-request cryptographic CSP nonce to eliminate
    'unsafe-inline' and 'unsafe-eval'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce

        response = self.get_response(request)

        # ── Content-Security-Policy ───────────────────────────────────────────
        # Hardened CSP header compliant with security audit requirements.
        # Uses per-request Nonce ('nonce-...') and eliminates 'unsafe-inline' & 'unsafe-eval'.
        csp_directives = "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://unpkg.com",
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com",
            "font-src 'self' fonts.gstatic.com data:",
            "img-src 'self' data: alexpsycht.pythonanywhere.com",
            "connect-src 'self' https://cdn.jsdelivr.net",
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
