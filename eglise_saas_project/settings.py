"""
=================================================================
SETTINGS — Configuration du projet Église SaaS
=================================================================
Ce fichier contrôle TOUT le comportement de Django.

GUIDE :
- INSTALLED_APPS : les "modules" activés dans le projet
- DATABASES : connexion à la base de données (SQLite par défaut)
- TEMPLATES : où Django cherche les fichiers HTML
- STATIC/MEDIA : où sont les CSS/JS/images
=================================================================
"""

from pathlib import Path

# Chemin racine du projet (c:/xampp/htdocs/eglise_saas)
BASE_DIR = Path(__file__).resolve().parent.parent

# === NOM DE LA PLATEFORME ===
# C'est ici qu'on change le nom affiché partout sur le site
APP_NAME = 'Église SaaS'

# Clé secrète — en production, mettez-la dans une variable d'environnement
SECRET_KEY = 'django-insecure-7sjm@9=8mwo^^%1$8ep-q1f3-tfw323d1&x*k&3+7(6r)=8mvl'

# Mode debug — à mettre sur False en production
DEBUG = True

ALLOWED_HOSTS = ['*']

# =============================================================
# APPLICATIONS INSTALLÉES
# =============================================================
# Chaque "app" est un module avec ses propres modèles, vues, etc.
# - django.contrib.* : apps intégrées à Django (admin, auth, etc.)
# - crispy_forms : rend les formulaires HTML plus jolis avec Bootstrap
# - church : NOTRE application principale
INSTALLED_APPS = [
    'django.contrib.admin',          # Interface d'administration Django
    'django.contrib.auth',           # Système d'authentification (login, users)
    'django.contrib.contenttypes',   # Suivi des types de modèles
    'django.contrib.sessions',       # Sessions utilisateur (rester connecté)
    'django.contrib.messages',       # Messages flash (succès, erreur, etc.)
    'django.contrib.staticfiles',    # Gestion des fichiers CSS/JS
    'django.contrib.humanize',       # Filtres d'affichage (dates, nombres)

    # Apps tierces
    'crispy_forms',                  # Formulaires Bootstrap
    'crispy_bootstrap5',             # Template pack Bootstrap 5

    # Notre app
    'church',                        # L'application église
]

# =============================================================
# MIDDLEWARE
# =============================================================
# Les middleware sont des "couches" que chaque requête HTTP traverse.
# Comme un système de sécurité à l'entrée d'un bâtiment.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',       # Sécurité HTTPS, headers
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
# DIRS : dossiers où Django cherche les templates
# APP_DIRS : cherche aussi dans church/templates/
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Notre dossier templates/ à la racine
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'church.context_processors.church_context',  # Notre context processor personnalisé
            ],
        },
    },
]

WSGI_APPLICATION = 'eglise_saas_project.wsgi.application'

# =============================================================
# BASE DE DONNÉES
# =============================================================
# On utilise SQLite pour le développement (pas besoin de MySQL).
# Le fichier db.sqlite3 sera créé automatiquement.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
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
LANGUAGE_CODE = 'fr-fr'          # Interface en français
TIME_ZONE = 'Africa/Lubumbashi'  # Fuseau horaire RDC (UTC+2)
USE_I18N = True                  # Activer les traductions
USE_TZ = True                    # Dates avec fuseau horaire

# =============================================================
# FICHIERS STATIQUES (CSS, JavaScript, Images du site)
# =============================================================
# STATIC_URL : URL pour accéder aux fichiers statiques
# STATICFILES_DIRS : dossiers contenant nos fichiers statiques
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# =============================================================
# FICHIERS MÉDIA (uploads des utilisateurs : logos, photos, etc.)
# =============================================================
# MEDIA_URL : URL pour accéder aux fichiers uploadés
# MEDIA_ROOT : dossier physique où ils sont stockés
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================
# CRISPY FORMS — Formulaires Bootstrap 5
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
