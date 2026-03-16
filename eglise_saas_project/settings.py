"""
=================================================================
SETTINGS â€” Configuration du projet Ã‰glise SaaS
=================================================================
Ce fichier contrÃ´le TOUT le comportement de Django.

GUIDE :
- INSTALLED_APPS : les "modules" activÃ©s dans le projet
- DATABASES : connexion Ã  la base de donnÃ©es (SQLite par dÃ©faut)
- TEMPLATES : oÃ¹ Django cherche les fichiers HTML
- STATIC/MEDIA : oÃ¹ sont les CSS/JS/images
=================================================================
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Chemin racine du projet (c:/xampp/htdocs/eglise_saas)
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

# === NOM DE LA PLATEFORME ===
# C'est ici qu'on change le nom affichÃ© partout sur le site
APP_NAME = 'Ã‰glise SaaS'

# ClÃ© secrÃ¨te â€” obligatoire via variable d'environnement
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY manquant. DÃ©finir la variable d'environnement SECRET_KEY.")

# Mode debug â€” False par dÃ©faut
DEBUG = os.environ.get('DEBUG', '').lower() == 'true'

allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1'] if DEBUG else []

# =============================================================
# APPLICATIONS INSTALLÃ‰ES
# =============================================================
# Chaque "app" est un module avec ses propres modÃ¨les, vues, etc.
# - django.contrib.* : apps intÃ©grÃ©es Ã  Django (admin, auth, etc.)
# - crispy_forms : rend les formulaires HTML plus jolis avec Bootstrap
# - church : NOTRE application principale
INSTALLED_APPS = [
    'django.contrib.admin',          # Interface d'administration Django
    'django.contrib.auth',           # SystÃ¨me d'authentification (login, users)
    'django.contrib.contenttypes',   # Suivi des types de modÃ¨les
    'django.contrib.sessions',       # Sessions utilisateur (rester connectÃ©)
    'django.contrib.messages',       # Messages flash (succÃ¨s, erreur, etc.)
    'django.contrib.staticfiles',    # Gestion des fichiers CSS/JS
    'django.contrib.humanize',       # Filtres d'affichage (dates, nombres)

    # Apps tierces
    'crispy_forms',                  # Formulaires Bootstrap
    'crispy_bootstrap5',             # Template pack Bootstrap 5

    # Notre app
    'church',                        # L'application Ã©glise
]

# =============================================================
# MIDDLEWARE
# =============================================================
# Les middleware sont des "couches" que chaque requÃªte HTTP traverse.
# Comme un systÃ¨me de sÃ©curitÃ© Ã  l'entrÃ©e d'un bÃ¢timent.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',       # SÃ©curitÃ© HTTPS, headers
    'whitenoise.middleware.WhiteNoiseMiddleware',           # Servir les fichiers statiques en production
    'django.contrib.sessions.middleware.SessionMiddleware', # Gestion des sessions
    'django.middleware.common.CommonMiddleware',            # URL trailing slash, etc.
    'django.middleware.csrf.CsrfViewMiddleware',           # Protection contre les attaques CSRF
    'django.contrib.auth.middleware.AuthenticationMiddleware', # Identification de l'utilisateur
    'django.contrib.messages.middleware.MessageMiddleware', # Messages flash
    'django.middleware.clickjacking.XFrameOptionsMiddleware', # Protection contre le clickjacking
]

ROOT_URLCONF = 'eglise_saas_project.urls'

# =============================================================
# TEMPLATES (fichiers HTML)
# =============================================================
# DIRS : dossiers oÃ¹ Django cherche les templates
# APP_DIRS : cherche aussi dans church/templates/
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Notre dossier templates/ Ã  la racine
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'church.context_processors.church_context',  # Notre context processor personnalisÃ©
            ],
        },
    },
]

WSGI_APPLICATION = 'eglise_saas_project.wsgi.application'

# =============================================================
# BASE DE DONNÃ‰ES
# =============================================================
# On utilise SQLite pour le dÃ©veloppement (pas besoin de MySQL).
# Le fichier db.sqlite3 sera crÃ©Ã© automatiquement.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'
    )
}

# Validation des mots de passe
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================
# LANGUE ET FUSEAU HORAIRE
# =============================================================
LANGUAGE_CODE = 'fr-fr'          # Interface en franÃ§ais
TIME_ZONE = 'Africa/Lubumbashi'  # Fuseau horaire RDC (UTC+2)
USE_I18N = True                  # Activer les traductions
USE_TZ = True                    # Dates avec fuseau horaire

# =============================================================
# FICHIERS STATIQUES (CSS, JavaScript, Images du site)
# =============================================================
# STATIC_URL : URL pour accÃ©der aux fichiers statiques
# STATICFILES_DIRS : dossiers contenant nos fichiers statiques
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# =============================================================
# FICHIERS MÃ‰DIA (uploads des utilisateurs : logos, photos, etc.)
# =============================================================
# MEDIA_URL : URL pour accÃ©der aux fichiers uploadÃ©s
# MEDIA_ROOT : dossier physique oÃ¹ ils sont stockÃ©s
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================
# CRISPY FORMS â€” Formulaires Bootstrap 5
# =============================================================
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# =============================================================
# AUTHENTIFICATION
# =============================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
