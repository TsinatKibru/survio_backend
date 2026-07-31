def csp_nonce(request):
    """Context processor to make request.csp_nonce available as {{ csp_nonce }} in all templates."""
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}
