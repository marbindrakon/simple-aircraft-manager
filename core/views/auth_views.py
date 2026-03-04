import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render
from django.views import View

from core.forms import RegistrationForm, UserProfileForm
from core.models import AircraftRole, InvitationCode, InvitationCodeRedemption

logger = logging.getLogger(__name__)

User = get_user_model()

def custom_logout(request):
    """
    Custom logout view that handles both OIDC and Django sessions.

    If the user has an OIDC session (indicated by oidc_id_token in session),
    redirect to the Keycloak logout endpoint to clear both sessions.
    Otherwise, perform standard Django logout.
    """
    # Check if OIDC is enabled and user has OIDC session
    if getattr(settings, 'OIDC_ENABLED', False) and 'oidc_id_token' in request.session:
        # Import here to avoid issues when mozilla_django_oidc is not installed
        from core.oidc import provider_logout

        # Get Keycloak logout URL
        logout_url = provider_logout(request)

        # Clear Django session
        logout(request)

        # Redirect to Keycloak logout (which will redirect back to our app)
        if logout_url:
            return redirect(logout_url)

    # Standard Django logout (for local users or if OIDC disabled)
    logout(request)
    return redirect('/')



class RegisterView(View):
    """Redeem an invitation code and create a local account."""

    def _get_code(self, token):
        try:
            return InvitationCode.objects.get(token=token)
        except InvitationCode.DoesNotExist:
            return None

    def get(self, request, token):
        if request.user.is_authenticated:
            return redirect('dashboard')

        code = self._get_code(token)
        if code is None or not code.is_valid:
            return render(request, 'registration/register.html', {'invalid': True})

        form = RegistrationForm(invited_email=code.invited_email, invited_name=code.invited_name)
        return render(request, 'registration/register.html', {'form': form, 'code': code})

    def post(self, request, token):
        if request.user.is_authenticated:
            return redirect('dashboard')

        code = self._get_code(token)
        if code is None or not code.is_valid:
            return render(request, 'registration/register.html', {'invalid': True})

        form = RegistrationForm(
            request.POST,
            invited_email=code.invited_email,
            invited_name=code.invited_name,
        )
        if not form.is_valid():
            return render(request, 'registration/register.html', {'form': form, 'code': code})

        try:
            with transaction.atomic():
                user = form.save()

                # Re-fetch with a row-level lock to prevent concurrent over-redemption
                code = InvitationCode.objects.select_for_update().get(pk=code.pk)
                if not code.is_valid:
                    raise ValueError("Invitation code is no longer valid")

                InvitationCodeRedemption.objects.create(code=code, user=user)
                InvitationCode.objects.filter(pk=code.pk).update(use_count=F('use_count') + 1)

                # Grant any configured initial aircraft roles
                for initial_role in code.initial_roles.select_related('aircraft').all():
                    AircraftRole.objects.get_or_create(
                        aircraft=initial_role.aircraft,
                        user=user,
                        defaults={'role': initial_role.role},
                    )
        except ValueError:
            return render(request, 'registration/register.html', {'invalid': True})

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('dashboard')


class ProfileView(LoginRequiredMixin, View):
    """Allow local-account users to edit their own profile."""

    def _check_local_account(self, request):
        """Return None if the user has a local account, or a redirect if not."""
        if not request.user.has_usable_password():
            return redirect('dashboard')
        return None

    def get(self, request):
        if redirect_response := self._check_local_account(request):
            return redirect_response
        form = UserProfileForm(instance=request.user)
        return render(request, 'core/profile.html', {'form': form})

    def post(self, request):
        if redirect_response := self._check_local_account(request):
            return redirect_response
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return render(request, 'core/profile.html', {'form': form, 'saved': True})
        return render(request, 'core/profile.html', {'form': form})

