# AGENTS.md — Église SaaS

## Build & Run
- **Dev server**: `python manage.py runserver`
- **Migrations**: `python manage.py makemigrations` then `python manage.py migrate`
- **All tests**: `python manage.py test`
- **Single test**: `python manage.py test church.tests.TestClassName.test_method_name`
- **Dependencies**: `pip install -r requirements.txt` (Django 5.1+, Pillow, crispy-forms, crispy-bootstrap5)

## Architecture
- **Django project** with one app: `church/`. Project config in `eglise_saas_project/`.
- **Database**: PostgreSQL only. Central model is `Church`; all others (Event, Sermon, Member, Page, ContactMessage) link to it via ForeignKey. `SiteSettings` is a singleton (pk=1).
- **URLs**: Public site at `/eglise/<slug>/`, admin dashboard at `/dashboard/`, Django admin at `/admin/`.
- **Templates**: `templates/` (root-level shared templates + `base.html`) and `church/templates/` (app-specific). Uses Bootstrap 5 via crispy-forms.
- **Static/Media**: `static/` for CSS/JS/images; `media/` for user uploads.

## Code Style
- Language: Python. Comments and model verbose_names are in **French**.
- Views are function-based with `@login_required` for dashboard views.
- Forms use `django-crispy-forms` with Bootstrap 5 template pack.
- Models use `verbose_name`, `ordering` in Meta, and `__str__`. Slugs auto-generated in `save()`.
- Imports: stdlib first, then Django, then local app (relative: `from .models import ...`).
- Settings: `LANGUAGE_CODE = 'fr-fr'`, `TIME_ZONE = 'Africa/Lubumbashi'`.
