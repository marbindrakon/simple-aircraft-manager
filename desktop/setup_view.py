"""First-run configuration page for the desktop launcher.

When the launcher boots without a ``config.ini`` it serves these views in
"setup mode": the user picks an auth mode, optionally sets a username +
password, and optionally configures one or more AI providers (Anthropic
API, local Ollama, OpenAI-compatible endpoint such as vLLM/OpenRouter).
When more than one is configured, the user picks which is the default in
the import-page model selector. Submitting the form writes ``config.ini``
to the user-data dir, creates the initial user (or the no-auth
``desktop`` user), stores any API keys in the OS keyring, and prompts
the user to restart the app.

These views are gated by:
1. The ``desktop`` app only being installed in ``settings_desktop`` —
   in dev/prod the URLs aren't registered and these views never load.
2. ``paths.config_ini_path()`` not existing — once setup has run, every
   subsequent GET/POST returns 404 so the page can't be reused to clobber
   credentials after the fact.

This is the cross-platform replacement for the Inno Setup wizard pages
that used to collect the same data on Windows.
"""

from __future__ import annotations

import json
import logging
import re

import keyring
from django.contrib.auth import get_user_model
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect

from desktop import paths
from desktop.bootstrap import DESKTOP_USERNAME
from desktop.config import (
    KEYRING_SERVICE,
    KEYRING_USERNAME,
    KEYRING_USERNAME_LITELLM,
    VALID_AUTH_MODES,
    VALID_DEFAULT_PROVIDERS,
)

# Ollama tag names are restricted to a safe character set: letters, digits,
# `_`, `-`, `.`, `:`, and `/` (for namespaced repos like `library/llama3`).
# Same shape works for OpenAI-compatible/LiteLLM model strings — they
# also tolerate `,` and `+` in some cases but those are unusual; tighten
# rather than widen the charset, the user can always edit config.ini for
# exotic IDs. We validate defensively even though we never shell out —
# the value flows straight into config.ini and JSON, both of which are
# text-safe formats.
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_\-./:]+$")

LOG = logging.getLogger(__name__)


def _ensure_setup_active() -> None:
    """Raise Http404 unless setup mode is genuinely active."""
    if paths.config_ini_path().exists():
        raise Http404("Setup has already been completed for this install.")


@method_decorator(csrf_protect, name="dispatch")
class DesktopSetupView(View):
    """Single-page setup form: auth mode + creds + optional API key."""

    template_name = "desktop_setup.html"

    def get(self, request, *args, **kwargs):
        _ensure_setup_active()
        return render(request, self.template_name, {"errors": {}, "values": {}})

    def post(self, request, *args, **kwargs):
        _ensure_setup_active()

        fields = {
            "auth_mode": request.POST.get("auth_mode", "").strip(),
            "username": request.POST.get("username", "").strip(),
            "password": request.POST.get("password", ""),
            "confirm_password": request.POST.get("confirm_password", ""),
            "api_key": request.POST.get("api_key", "").strip(),
            "ollama_model": request.POST.get("ollama_model", "").strip(),
            "ollama_base_url": request.POST.get("ollama_base_url", "").strip(),
            "litellm_model": request.POST.get("litellm_model", "").strip(),
            "litellm_base_url": request.POST.get("litellm_base_url", "").strip(),
            "litellm_api_key": request.POST.get("litellm_api_key", "").strip(),
            "default_provider": request.POST.get("default_provider", "").strip().lower(),
        }

        errors = _validate(**fields)
        # Don't echo passwords or API keys back into the form.
        values = {k: v for k, v in fields.items() if k not in {
            "password", "confirm_password", "api_key", "litellm_api_key",
        }}
        if errors:
            return render(
                request,
                self.template_name,
                {"errors": errors, "values": values},
                status=400,
            )

        try:
            _apply_setup(**fields)
        except Exception:
            LOG.exception("Desktop setup failed")
            return render(
                request,
                self.template_name,
                {
                    "errors": {"form": "Could not save setup. Check the launcher log."},
                    "values": values,
                },
                status=500,
            )

        # Success page: tells the user to restart.
        return render(request, "desktop_setup_done.html", {})


def _validate(
    *,
    auth_mode: str,
    username: str,
    password: str,
    confirm_password: str,
    api_key: str,
    ollama_model: str,
    ollama_base_url: str,
    litellm_model: str,
    litellm_base_url: str,
    litellm_api_key: str,
    default_provider: str,
) -> dict[str, str]:
    errors: dict[str, str] = {}

    if auth_mode not in VALID_AUTH_MODES:
        errors["auth_mode"] = "Choose an authentication mode."
        return errors

    if auth_mode == "required":
        if len(username) < 3:
            errors["username"] = "Username must be at least 3 characters."
        if len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        if password != confirm_password:
            errors["confirm_password"] = "Passwords do not match."

    if ollama_model:
        if not _MODEL_NAME_RE.match(ollama_model):
            errors["ollama_model"] = (
                "Use only letters, digits, and `_-./:` — e.g. `llama3.2-vision`."
            )
        if ollama_base_url and not _is_http_url(ollama_base_url):
            errors["ollama_base_url"] = "Must start with http:// or https://."

    if litellm_model:
        if not _MODEL_NAME_RE.match(litellm_model):
            errors["litellm_model"] = (
                "Use only letters, digits, and `_-./:` — e.g. `gpt-4o-mini` or "
                "`anthropic/claude-sonnet-4-6`."
            )
        if not litellm_base_url:
            errors["litellm_base_url"] = (
                "Required when a custom model is set — e.g. "
                "`https://openrouter.ai/api/v1` or `http://localhost:8000/v1`."
            )
        elif not _is_http_url(litellm_base_url):
            errors["litellm_base_url"] = "Must start with http:// or https://."

    configured = _configured_providers(
        api_key=api_key, ollama_model=ollama_model, litellm_model=litellm_model,
    )
    if default_provider:
        if default_provider not in VALID_DEFAULT_PROVIDERS:
            errors["default_provider"] = "Choose a configured provider."
        elif default_provider not in configured:
            errors["default_provider"] = (
                "The default must point at a provider you've filled in."
            )
    elif len(configured) > 1:
        errors["default_provider"] = (
            "Pick a default provider when more than one is configured."
        )

    return errors


def _configured_providers(*, api_key: str, ollama_model: str, litellm_model: str) -> set[str]:
    out: set[str] = set()
    if api_key:
        out.add("anthropic")
    if ollama_model:
        out.add("ollama")
    if litellm_model:
        out.add("litellm")
    return out


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _apply_setup(
    *,
    auth_mode: str,
    username: str,
    password: str,
    confirm_password: str = "",  # accepted for symmetry with _validate; unused here
    api_key: str,
    ollama_model: str = "",
    ollama_base_url: str = "",
    litellm_model: str = "",
    litellm_base_url: str = "",
    litellm_api_key: str = "",
    default_provider: str = "",
) -> None:
    """Persist the user's choices: write config.ini, create the initial
    user, and store any API keys in the OS keyring. Order matters — config.ini
    is written LAST so a partial failure leaves setup mode active."""

    paths.ensure_dirs()

    UserModel = get_user_model()
    if auth_mode == "required":
        if not UserModel.objects.filter(username=username).exists():
            UserModel.objects.create_superuser(username=username, email="", password=password)
            LOG.info("Created bootstrap superuser %r via desktop setup", username)
    else:
        # No-auth mode: create the placeholder user the auto-login middleware
        # binds onto every request. Mirrors desktop.bootstrap._ensure_desktop_user.
        user, created = UserModel.objects.get_or_create(
            username=DESKTOP_USERNAME,
            defaults={"is_active": True},
        )
        if created:
            user.set_unusable_password()
            user.save()
        paths.desktop_user_path().write_text(
            json.dumps({"user_pk": user.pk}), encoding="utf-8",
        )

    if api_key:
        _store_secret(KEYRING_USERNAME, api_key)
    if litellm_api_key:
        _store_secret(KEYRING_USERNAME_LITELLM, litellm_api_key)

    sections = [f"[auth]\nmode = {auth_mode}\n"]
    ai_lines = _build_ai_section_lines(
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url,
        litellm_model=litellm_model,
        litellm_base_url=litellm_base_url,
        default_provider=_effective_default_provider(
            default_provider,
            api_key=api_key,
            ollama_model=ollama_model,
            litellm_model=litellm_model,
        ),
    )
    if ai_lines:
        sections.append("[ai]\n" + "\n".join(ai_lines) + "\n")

    config_path = paths.config_ini_path()
    config_path.write_text("\n".join(sections), encoding="utf-8")


def _store_secret(username: str, value: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, username, value)
    except Exception as e:
        # Don't block setup completion if keyring isn't usable — the user
        # can re-add the secret later via the OS credential manager.
        LOG.warning("Could not save %r to OS keystore: %s", username, e)


def _effective_default_provider(
    raw: str, *, api_key: str, ollama_model: str, litellm_model: str
) -> str:
    """Persist a default_provider value when there's a meaningful choice
    to make. With zero or one provider configured, omit the key — the
    loader will infer correctly and writing it just creates noise."""
    if raw and raw in VALID_DEFAULT_PROVIDERS:
        return raw
    return ""


def _build_ai_section_lines(
    *,
    ollama_model: str,
    ollama_base_url: str,
    litellm_model: str,
    litellm_base_url: str,
    default_provider: str,
) -> list[str]:
    lines: list[str] = []
    if default_provider:
        lines.append(f"default_provider = {default_provider}")
    if ollama_model:
        lines.append(f"ollama_model = {ollama_model}")
        if ollama_base_url:
            lines.append(f"ollama_base_url = {ollama_base_url}")
    if litellm_model:
        lines.append(f"litellm_model = {litellm_model}")
        if litellm_base_url:
            lines.append(f"litellm_base_url = {litellm_base_url}")
    return lines


def setup_status(request):
    """Tiny JSON endpoint the success page can poll if desired."""
    return JsonResponse({"setup_complete": paths.config_ini_path().exists()})
