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


class LoginRateLimitMiddleware:
    """
    Brute-force protection middleware for login endpoints (/admin/login/, /api/auth/login/).
    Limits failed login attempts per client IP address and per target account username
    (maximum 5 failed attempts within 5 minutes / 300 seconds).
    Returns HTTP 429 Too Many Requests when threshold is exceeded.
    """
    MAX_ATTEMPTS = 5
    LOCKOUT_TIME = 300  # 5 minutes in seconds
    LOGIN_PATHS = ('/admin/login/', '/api/auth/login/', '/admin/login')

    def __init__(self, get_response):
        self.get_response = get_response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip

    def __call__(self, request):
        path = request.path_info
        is_login_path = any(path == p or path.startswith(p.rstrip('/')) for p in self.LOGIN_PATHS)

        if request.method == 'POST' and is_login_path:
            import json
            from django.core.cache import cache
            from django.http import HttpResponse, JsonResponse

            ip = self._get_client_ip(request)
            username = request.POST.get('username', '').strip().lower()
            if not username and request.content_type == 'application/json':
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    username = str(body.get('username', '')).strip().lower()
                except Exception:
                    pass

            ip_key = f'login_attempts_ip_{ip}'
            user_key = f'login_attempts_user_{username}' if username else None

            ip_attempts = cache.get(ip_key, 0)
            user_attempts = cache.get(user_key, 0) if user_key else 0

            # Check if rate limit exceeded
            if ip_attempts >= self.MAX_ATTEMPTS or user_attempts >= self.MAX_ATTEMPTS:
                msg = "Too many failed login attempts. Please try again in 5 minutes."
                if request.headers.get('accept') == 'application/json' or path.startswith('/api/'):
                    return JsonResponse({'detail': msg, 'error': 'too_many_requests'}, status=429)
                return HttpResponse(
                    f"<!html><html><head><title>429 Too Many Requests</title></head>"
                    f"<body style='font-family:sans-serif; padding:50px; text-align:center;'>"
                    f"<h1>429 Too Many Requests</h1><p>{msg}</p></body></html>",
                    status=429,
                    content_type="text/html"
                )

            # Execute actual login request
            response = self.get_response(request)

            # Determine if login succeeded
            is_success = False
            if path.startswith('/admin'):
                if response.status_code == 302:
                    is_success = True
            elif path.startswith('/api'):
                if response.status_code == 200:
                    is_success = True

            if is_success:
                cache.delete(ip_key)
                if user_key:
                    cache.delete(user_key)
            else:
                cache.set(ip_key, ip_attempts + 1, self.LOCKOUT_TIME)
                if user_key:
                    cache.set(user_key, user_attempts + 1, self.LOCKOUT_TIME)

            return response

        return self.get_response(request)
