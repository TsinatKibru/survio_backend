from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class JWTAuthenticationWithRevocation(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to verify if the access token's 'iat' (issued-at)
    timestamp is prior to the user's 'last_logout' timestamp. If so, rejects the token
    with HTTP 401 Unauthorized (Token Has Been Revoked).
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        iat = validated_token.get('iat')
        if iat and user and getattr(user, 'last_logout', None):
            token_issued_at = datetime.fromtimestamp(iat, tz=dt_timezone.utc)
            if token_issued_at < user.last_logout:
                raise AuthenticationFailed('Token has been revoked upon logout.', code='token_revoked')

        return user, validated_token
