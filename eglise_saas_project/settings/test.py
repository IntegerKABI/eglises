"""Test settings profile."""

import os

os.environ.setdefault("DEBUG", "False")

from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eglise-saas-tests",
    }
}

# Keep expected request noise out of the test runner output.
LOGGING["loggers"]["django.request"] = {
    "handlers": ["console"],
    "level": "CRITICAL",
    "propagate": False,
}
