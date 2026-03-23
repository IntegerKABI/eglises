from django.core.cache import cache
from django.utils import timezone
from functools import wraps

def get_church_cache_version(church_slug=None):
    key = "global_home_version" if church_slug is None else f"church_v_{church_slug}"
    version = cache.get(key)
    if not version:
        version = str(timezone.now().timestamp())
        cache.set(key, version, timeout=None)
    return version

def bump_church_cache_version(church_slug=None):
    key = "global_home_version" if church_slug is None else f"church_v_{church_slug}"
    cache.set(key, str(timezone.now().timestamp()), timeout=None)

def cache_public_view(key_prefix_func):
    """
    Cache a public view indefinitely using versioned keys.
    Automatically bypassed if user is authenticated or query params (search) exist.
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
                cache.set(cache_key, response, timeout=60*60*24*30) # 30 Days
            return response
        return _wrapped_view
    return decorator
