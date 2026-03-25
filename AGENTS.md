# AGENTS.md — Église SaaS

## Build & Run
- **Dev server**: `python manage.py runserver`
- **Migrations**: `python manage.py makemigrations` then `python manage.py migrate`
- **All tests**: `python manage.py test`
- **Single test**: `python manage.py test church.tests.TestClassName.test_method_name`
- **Dependencies**: `pip install -r requirements.txt` (Django 5.1+, Pillow, crispy-forms, crispy-bootstrap5)

## Architecture
- **Django project** with two apps: `accounts/` and `church/`. Project config is in `eglise_saas_project/`.
- **Database**: PostgreSQL only. Central model is `Church`; all other domain models link to it through ForeignKey relationships or tenant-scoped relations. `SiteSettings` is a singleton (`pk=1`).
- **Models**: canonical code lives in `church/models/tenant.py`, `church/models/content.py`, and `church/models/communication.py`, with `church/models/__init__.py` as the public model surface.
- **Views**: canonical code lives in `accounts/views.py` and `church/views/` (`views.py`, `public.py`, `notification.py`, `superadmin.py`).
- **Helpers**: shared view/query/form/http helpers live under `church/helpers/`.
- **Services**: transactional business logic lives under `church/services/`.
- **Context**: request-context and context processors live under `church/context/`.
- **URLs**: public site at `/eglise/<slug>/`, admin dashboard at `/dashboard/`, Django admin at `/admin/`.
- **Templates**: `templates/` (root-level shared templates + `base.html`) and `church/templates/` (app-specific). Uses Bootstrap 5 via crispy-forms.
- **Static/Media**: `static/` for CSS/JS/images; `media/` for user uploads.

## Code Style
- Language: code internals, comments, docstrings, and log messages are in **English**.
- User-facing output stays in **French**.
- Views should stay focused on request handling and response shaping; business logic belongs in services.
- Forms should validate input shape and call services for persistence.
- Models should define data structure and simple derived properties only.
- Forms use `django-crispy-forms` with the Bootstrap 5 template pack.
- Models use `verbose_name`, `ordering` in `Meta`, and `__str__`. Slugs are auto-generated in `save()`.
- Imports: stdlib first, then Django, then local app imports.
- Settings: `LANGUAGE_CODE = 'fr-fr'`, `TIME_ZONE = 'Africa/Lubumbashi'`.
