"""Shared helpers for paginated list views in the church app."""

from django.core.paginator import Paginator

from .http import _querystring_without_page


def build_paginated_list_context(*, request, queryset, per_page, item_key):
    """Paginate a queryset and return the standard list-view context payload."""
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    return {
        item_key: page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    }
