"""Shared Django settings used by all runtime environments."""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(path):
    """Load a local dotenv file without overriding existing environment values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_bool(name, default=False):
    """Parse a boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    """Parse an integer environment variable."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_list(name, default=None):
    """Parse a comma-separated environment variable into a list."""
    raw_value = os.environ.get(name, "")
    values = [value.strip() for value in raw_value.split(",") if value.strip()]
    return values or list(default or [])


def _env_log_level(name, default="INFO"):
    """Parse and normalize a logging level environment variable."""
    value = os.environ.get(name, default)
    normalized = value.strip().upper()
    allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    return normalized if normalized in allowed_levels else default


def _build_database_config():
    """Build the PostgreSQL database configuration from environment variables."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    debug_enabled = _env_bool("DEBUG", default=False)

    if database_url:
        config = {
            **dj_database_url.parse(
                database_url,
                conn_max_age=_env_int("DATABASE_CONN_MAX_AGE", 600),
                ssl_require=_env_bool("DATABASE_SSL_REQUIRE", not debug_enabled),
            ),
            "CONN_HEALTH_CHECKS": True,
        }
        engine = config.get("ENGINE", "")
        if not engine.startswith("django.db.backends.postgresql"):
            raise ImproperlyConfigured("DATABASE_URL must point to PostgreSQL.")
        return config

    postgres_name = os.environ.get("POSTGRES_DB", "").strip()
    postgres_user = os.environ.get("POSTGRES_USER", "").strip()
    postgres_password = os.environ.get("POSTGRES_PASSWORD", "").strip()
    postgres_host = os.environ.get("POSTGRES_HOST", "").strip()
    postgres_port = os.environ.get("POSTGRES_PORT", "5432").strip() or "5432"

    if all([postgres_name, postgres_user, postgres_password, postgres_host]):
        options = {}
        if _env_bool("DATABASE_SSL_REQUIRE", default=False):
            options["sslmode"] = "require"
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": postgres_name,
            "USER": postgres_user,
            "PASSWORD": postgres_password,
            "HOST": postgres_host,
            "PORT": postgres_port,
            "CONN_MAX_AGE": _env_int("DATABASE_CONN_MAX_AGE", 600),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": options,
        }

    raise ImproperlyConfigured(
        "PostgreSQL configuration is required. Set DATABASE_URL or POSTGRES_DB, "
        "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_HOST."
    )


_load_dotenv(BASE_DIR / ".env")

APP_NAME = os.environ.get("APP_NAME", "Eglise SaaS")

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY manquant. Definir la variable d'environnement SECRET_KEY.")

DEBUG = _env_bool("DEBUG", default=False)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"] if DEBUG else [])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "crispy_forms",
    "crispy_bootstrap5",
    "accounts",
    "church",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "church.middleware.CurrentChurchMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "eglise_saas_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "church.context.processors.church_context",
            ],
        },
    },
]

WSGI_APPLICATION = "eglise_saas_project.wsgi.application"
ASGI_APPLICATION = "eglise_saas_project.asgi.application"

DATABASES = {
    "default": _build_database_config(),
}

CACHE_URL = os.environ.get("CACHE_URL")
if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
        }
    }

SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)
if _env_bool("USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "fr-fr")
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Lubumbashi")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_PORT = _env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
BACKGROUND_JOBS_EAGER = _env_bool("BACKGROUND_JOBS_EAGER", default=False)
CONTACT_EMAIL_ESCALATION_DELAY_SECONDS = _env_int("CONTACT_EMAIL_ESCALATION_DELAY_SECONDS", 60)

RATE_LIMITS = {
    "login_ip": {"limit": 10, "window": 900},
    "login_account": {"limit": 5, "window": 900},
    "contact_ip": {"limit": 5, "window": 900},
    "contact_email": {"limit": 3, "window": 900},
    "invite_accept_ip": {"limit": 10, "window": 1800},
    "invite_accept_identity": {"limit": 5, "window": 1800},
    "invite_send_ip": {"limit": 20, "window": 3600},
    "invite_send_actor": {"limit": 10, "window": 3600},
}

LOG_LEVEL = _env_log_level("LOG_LEVEL", default="DEBUG" if DEBUG else "INFO")
DJANGO_LOG_LEVEL = _env_log_level("DJANGO_LOG_LEVEL", default="INFO")
DJANGO_SERVER_LOG_LEVEL = _env_log_level("DJANGO_SERVER_LOG_LEVEL", default="ERROR")
CHURCH_LOG_LEVEL = _env_log_level("CHURCH_LOG_LEVEL", default=LOG_LEVEL)
BACKGROUND_JOBS_LOG_LEVEL = _env_log_level("BACKGROUND_JOBS_LOG_LEVEL", default=LOG_LEVEL)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": (
                "timestamp=%(asctime)s level=%(levelname)s logger=%(name)s "
                "module=%(module)s function=%(funcName)s line=%(lineno)d message=%(message)s"
            ),
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": DJANGO_SERVER_LOG_LEVEL,
            "propagate": False,
        },
        "church": {
            "handlers": ["console"],
            "level": CHURCH_LOG_LEVEL,
            "propagate": False,
        },
        "church.background_jobs": {
            "handlers": ["console"],
            "level": BACKGROUND_JOBS_LOG_LEVEL,
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
