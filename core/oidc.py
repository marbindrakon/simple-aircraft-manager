"""
OIDC Authentication Backend for Keycloak Integration

This module provides a custom OIDC authentication backend that extends
mozilla-django-oidc to handle user creation, updates, and logout.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def generate_username(email):
    """
    Generate a username from an email address.
    Takes the local part before @ and ensures uniqueness.

    Args:
        email: Email address string

    Returns:
        Unique username string
    """
    if not email or '@' not in email:
        return None

    # Get local part of email
    base_username = email.split('@')[0]
    # Remove any characters that aren't alphanumeric, underscore, or hyphen
    base_username = ''.join(c for c in base_username if c.isalnum() or c in '_-')

    if not base_username:
        return None

    # Ensure uniqueness
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    return username


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Custom OIDC backend for Keycloak integration.

    Handles:
    - Auto-creation of Django users from OIDC claims
    - Syncing user attributes on each login
    - Flexible username generation
    """

    def create_user(self, claims):
        """
        Create a new Django user from OIDC claims.

        Args:
            claims: Dictionary of OIDC claims from Keycloak

        Returns:
            User object
        """
        email = claims.get(getattr(settings, 'OIDC_EMAIL_CLAIM', 'email'))
        username = self.get_username(claims)

        if not username:
            logger.error("Cannot create user: no valid username in claims")
            return None

        try:
            user = User.objects.create_user(username=username, email=email or '')
        except IntegrityError:
            logger.warning(f"IntegrityError creating user '{username}': likely a concurrent signup")
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                logger.error(f"Cannot retrieve user '{username}' after IntegrityError")
                return None

        self.update_user(user, claims)
        logger.info(f"Created new user from OIDC: {username} ({email})")
        return user

    def update_user(self, user, claims):
        """
        Update existing user attributes from OIDC claims.
        Called on every login to keep user data in sync.

        Args:
            user: Django User object
            claims: Dictionary of OIDC claims from Keycloak

        Returns:
            Updated User object
        """
        # Update email
        email = claims.get(getattr(settings, 'OIDC_EMAIL_CLAIM', 'email'))
        if email:
            user.email = email

        # Update first name
        first_name_claim = getattr(settings, 'OIDC_FIRSTNAME_CLAIM', 'given_name')
        first_name = claims.get(first_name_claim)
        if first_name:
            user.first_name = first_name

        # Update last name
        last_name_claim = getattr(settings, 'OIDC_LASTNAME_CLAIM', 'family_name')
        last_name = claims.get(last_name_claim)
        if last_name:
            user.last_name = last_name

        user.save()

        # Store OIDC sub for future lookups (prevents account takeover on username rename)
        sub = claims.get('sub')
        if sub:
            from core.models import UserProfile
            UserProfile.objects.update_or_create(user=user, defaults={'oidc_sub': sub})

        logger.debug(f"Updated user from OIDC claims: {user.username}")
        return user

    def get_username(self, claims):
        """
        Extract or generate username from OIDC claims.

        Priority order:
        1. preferred_username (Keycloak standard) — sanitized
        2. email local part
        3. sub (OIDC subject identifier)

        Args:
            claims: Dictionary of OIDC claims

        Returns:
            Username string
        """
        # Try preferred_username first (Keycloak standard), sanitized
        username = claims.get('preferred_username')
        if username:
            sanitized = ''.join(c for c in username if c.isalnum() or c in '_-')
            if sanitized:
                return sanitized

        # Try generating from email
        email = claims.get(getattr(settings, 'OIDC_EMAIL_CLAIM', 'email'))
        if email:
            username = generate_username(email)
            if username:
                return username

        # Fallback to sub (OIDC subject - usually a UUID)
        return claims.get('sub')

    def filter_users_by_claims(self, claims):
        """
        Filter users by OIDC claims to find existing user.

        Looks up by OIDC subject (sub) first to prevent account takeover
        when preferred_username changes. Falls back to username match for
        accounts created before sub tracking was introduced.

        Args:
            claims: Dictionary of OIDC claims

        Returns:
            QuerySet of matching users
        """
        from core.models import UserProfile
        sub = claims.get('sub')
        if sub:
            try:
                profile = UserProfile.objects.select_related('user').get(oidc_sub=sub)
                return User.objects.filter(pk=profile.user_id)
            except UserProfile.DoesNotExist:
                pass

        # Fallback: username match (handles accounts created before sub tracking)
        username = self.get_username(claims)
        if not username:
            return User.objects.none()
        return User.objects.filter(username=username)


def provider_logout(request):
    """
    Construct OIDC provider logout URL for RP-initiated logout.

    This performs a full logout from the OIDC provider, not just the Django session.

    Args:
        request: Django request object

    Returns:
        OIDC logout URL string, or None if no endpoint is configured
    """
    logout_endpoint = getattr(settings, 'OIDC_OP_LOGOUT_ENDPOINT', None)

    if not logout_endpoint:
        # Fall back to constructing from discovery endpoint (Keycloak-specific path)
        discovery_endpoint = getattr(settings, 'OIDC_OP_DISCOVERY_ENDPOINT', '')
        if not discovery_endpoint:
            logger.warning("No OIDC logout endpoint configured")
            return None
        base_url = discovery_endpoint.replace('/.well-known/openid-configuration', '')
        logout_endpoint = f"{base_url}/protocol/openid-connect/logout"

    # Get post logout redirect URI (where provider sends user after logout)
    post_logout_redirect_uri = request.build_absolute_uri('/')

    # Get id_token_hint from session if available (recommended by OIDC spec)
    id_token = request.session.get('oidc_id_token')

    params = {'post_logout_redirect_uri': post_logout_redirect_uri}
    if id_token:
        params['id_token_hint'] = id_token

    logout_url = f"{logout_endpoint}?{urlencode(params)}"
    logger.debug(f"Constructed OIDC logout URL: {logout_url}")
    return logout_url
