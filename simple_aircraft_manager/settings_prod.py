"""
Production settings for simple_aircraft_manager project.
Designed for OpenShift deployment.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings from environment variables (no unsafe defaults)
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.environ['DJANGO_ALLOWED_HOSTS'].split(',')

# CSRF trusted origins for OpenShift routes
CSRF_TRUSTED_ORIGINS = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]

# Media and static files
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', '/opt/app-root/src/mediafiles')
MEDIA_URL = '/media/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', '/opt/app-root/src/staticfiles')
STATIC_URL = '/static/'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated'
    ]
}

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'core',
    'health',
]

# OIDC Configuration
OIDC_ENABLED = os.environ.get('OIDC_ENABLED', 'False').lower() in ('true', '1', 'yes')

if OIDC_ENABLED:
    # Add mozilla-django-oidc to installed apps
    INSTALLED_APPS.append('mozilla_django_oidc')

    # OIDC Provider Configuration (required)
    OIDC_OP_DISCOVERY_ENDPOINT = os.environ['OIDC_OP_DISCOVERY_ENDPOINT']
    OIDC_RP_CLIENT_ID = os.environ['OIDC_RP_CLIENT_ID']
    OIDC_RP_CLIENT_SECRET = os.environ['OIDC_RP_CLIENT_SECRET']

    # Fetch OIDC endpoints from discovery document
    import requests
    try:
        discovery_response = requests.get(OIDC_OP_DISCOVERY_ENDPOINT, timeout=10)
        discovery_response.raise_for_status()
        discovery_doc = discovery_response.json()

        OIDC_OP_AUTHORIZATION_ENDPOINT = discovery_doc['authorization_endpoint']
        OIDC_OP_TOKEN_ENDPOINT = discovery_doc['token_endpoint']
        OIDC_OP_USER_ENDPOINT = discovery_doc['userinfo_endpoint']
        OIDC_OP_JWKS_ENDPOINT = discovery_doc.get('jwks_uri')
        OIDC_OP_LOGOUT_ENDPOINT = discovery_doc.get('end_session_endpoint')
    except Exception as e:
        import sys
        print(f"ERROR: Failed to fetch OIDC discovery document from {OIDC_OP_DISCOVERY_ENDPOINT}: {e}", file=sys.stderr)
        print("OIDC authentication will not be available", file=sys.stderr)
        # Don't crash on startup - just disable OIDC
        OIDC_ENABLED = False

    if OIDC_ENABLED:
        # OIDC Optional Configuration
        OIDC_RP_SIGN_ALGO = os.environ.get('OIDC_RP_SIGN_ALGO', 'RS256')
        OIDC_RP_SCOPES = os.environ.get('OIDC_RP_SCOPES', 'openid email profile')

        # Claim Mappings
        OIDC_EMAIL_CLAIM = os.environ.get('OIDC_EMAIL_CLAIM', 'email')
        OIDC_FIRSTNAME_CLAIM = os.environ.get('OIDC_FIRSTNAME_CLAIM', 'given_name')
        OIDC_LASTNAME_CLAIM = os.environ.get('OIDC_LASTNAME_CLAIM', 'family_name')

        # Username Algorithm
        OIDC_USERNAME_ALGO = 'core.oidc.generate_username'

        # Token Expiry (seconds)
        OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = int(os.environ.get('OIDC_TOKEN_EXPIRY', '3600'))

        # Authentication Backends
        AUTHENTICATION_BACKENDS = [
            'core.oidc.CustomOIDCAuthenticationBackend',
            'django.contrib.auth.backends.ModelBackend',  # Fallback for local users
        ]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'simple_aircraft_manager.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.oidc_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'simple_aircraft_manager.wsgi.application'

# Database configuration from environment
# Supports PostgreSQL (recommended) or SQLite for development
DATABASE_ENGINE = os.environ.get('DATABASE_ENGINE', 'sqlite3')

if DATABASE_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DATABASE_NAME', 'aircraft_manager'),
            'USER': os.environ.get('DATABASE_USER', 'postgres'),
            'PASSWORD': os.environ.get('DATABASE_PASSWORD', ''),
            'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
            'PORT': os.environ.get('DATABASE_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('DATABASE_PATH', '/opt/app-root/src/data/db.sqlite3'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TZ', 'UTC')
USE_I18N = True
USE_TZ = True

# Login redirect
LOGIN_REDIRECT_URL = '/dashboard'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logbook import AI model configuration
LOGBOOK_IMPORT_MODELS = [
    {
        'id': 'claude-sonnet-4-5-20250929',
        'name': 'Sonnet 4.5 (recommended)',
        'provider': 'anthropic',
    },
    {
        'id': 'claude-haiku-4-5-20251001',
        'name': 'Haiku 4.5 (faster / cheaper)',
        'provider': 'anthropic',
    },
    {
        'id': 'claude-opus-4-6',
        'name': 'Opus 4.6 (highest quality)',
        'provider': 'anthropic',
    },
]

# Add extra models (e.g. Ollama) via JSON env var without rebuilding the image:
#   LOGBOOK_IMPORT_EXTRA_MODELS='[{"id":"llama3.2-vision","name":"Llama 3.2 Vision (local)","provider":"ollama"}]'
_extra_models_json = os.environ.get('LOGBOOK_IMPORT_EXTRA_MODELS')
if _extra_models_json:
    import json as _json
    LOGBOOK_IMPORT_MODELS += _json.loads(_extra_models_json)

LOGBOOK_IMPORT_DEFAULT_MODEL = os.environ.get(
    'LOGBOOK_IMPORT_DEFAULT_MODEL', 'claude-sonnet-4-5-20250929'
)

# Ollama connection (only needed if any model uses provider=ollama)
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 'yes')
    CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True').lower() in ('true', '1', 'yes')
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
