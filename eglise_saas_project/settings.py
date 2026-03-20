"""Django settings for the Eglise SaaS project."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / '.env')


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name, default):
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _build_database_config():
    sqlite_url = f'sqlite:///{BASE_DIR / "db.sqlite3"}'
    database_url = os.environ.get('DATABASE_URL', '').strip()
    debug_enabled = _env_bool('DEBUG', default=False)

    if database_url:
        return {
            **dj_database_url.parse(
                database_url,
                conn_max_age=_env_int('DATABASE_CONN_MAX_AGE', 600),
                ssl_require=_env_bool('DATABASE_SSL_REQUIRE', not debug_enabled),
            ),
            'CONN_HEALTH_CHECKS': True,
        }

    postgres_name = os.environ.get('POSTGRES_DB', '').strip()
    postgres_user = os.environ.get('POSTGRES_USER', '').strip()
    postgres_password = os.environ.get('POSTGRES_PASSWORD', '').strip()
    postgres_host = os.environ.get('POSTGRES_HOST', '').strip()
    postgres_port = os.environ.get('POSTGRES_PORT', '5432').strip() or '5432'

    if all([postgres_name, postgres_user, postgres_password, postgres_host]):
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': postgres_name,
            'USER': postgres_user,
            'PASSWORD': postgres_password,
            'HOST': postgres_host,
            'PORT': postgres_port,
            'CONN_MAX_AGE': _env_int('DATABASE_CONN_MAX_AGE', 600),
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {},
        }

    return dj_database_url.parse(sqlite_url, conn_max_age=0)


APP_NAME = 'Eglise SaaS'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY manquant. Definir la variable d'environnement SECRET_KEY.")

DEBUG = _env_bool('DEBUG', default=False)

allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
if allowed_hosts_env:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1'] if DEBUG else []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'crispy_bootstrap5',
    'accounts',
    'church',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'church.middleware.CurrentChurchMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'eglise_saas_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'church.context_processors.church_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'eglise_saas_project.wsgi.application'

DATABASES = {
    'default': _build_database_config(),
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Lubumbashi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'
