"""Versioned cache helpers for public church pages."""

from functools import wraps
from uuid import uuid4

from django.core.cache import cache


GLOBAL_HOME_CACHE_VERSION_KEY = "public:home:version"
SITE_PUBLIC_CACHE_VERSION_KEY = "public:site:version"
CHURCH_CACHE_VERSION_KEY_TEMPLATE = "public:church:{slug}:version"


def _generate_cache_version():
    """Return a unique cache version token."""
    return uuid4().hex


def _get_or_set_version(key):
    """Return the current cache version for a key, creating it when missing."""
    version = cache.get(key)
    if version is None:
        version = _generate_cache_version()
        cache.set(key, version, timeout=None)
    return version


def get_site_cache_version():
    """Return the global site-level public cache version."""
    return _get_or_set_version(SITE_PUBLIC_CACHE_VERSION_KEY)


def get_church_cache_version(church_slug=None):
    """Return the effective public cache version for the global site or a church."""
    church_key = (
        GLOBAL_HOME_CACHE_VERSION_KEY
        if church_slug is None
        else CHURCH_CACHE_VERSION_KEY_TEMPLATE.format(slug=church_slug)
    )
    site_version = get_site_cache_version()
    church_version = _get_or_set_version(church_key)
    return f"{site_version}:{church_version}"

def bump_church_cache_version(church_slug=None):
    """Invalidate the cache version for the global home page or a specific church."""
    key = (
        GLOBAL_HOME_CACHE_VERSION_KEY
        if church_slug is None
        else CHURCH_CACHE_VERSION_KEY_TEMPLATE.format(slug=church_slug)
    )
    cache.set(key, _generate_cache_version(), timeout=None)


def bump_site_cache_version():
    """Invalidate all public cache entries that depend on site-wide settings."""
    cache.set(SITE_PUBLIC_CACHE_VERSION_KEY, _generate_cache_version(), timeout=None)


def cache_public_view(key_prefix_func):
    """
    Cache a public view with versioned keys while bypassing authenticated or filtered requests.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.GET or request.user.is_authenticated:
                return view_func(request, *args, **kwargs)

            cache_key = key_prefix_func(request, *args, **kwargs)
            response = cache.get(cache_key)
            if response:
                return response

            response = view_func(request, *args, **kwargs)
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache.set(cache_key, response, timeout=60 * 60 * 24 * 30)  # Keep public pages warm for a month.
            return response
        return _wrapped_view
    return decorator
