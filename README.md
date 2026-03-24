# Église SaaS

Plateforme SaaS multi-tenant pour églises, construite avec Django. Chaque église dispose de son espace public, de son tableau de bord, de ses utilisateurs, de ses invitations, de ses contenus, de ses messages, de ses notifications et de ses limites de plan.

## Vue d'ensemble

Le projet couvre deux surfaces principales :

- Site public
  - page d'accueil globale avec la liste des églises actives
  - site public propre à chaque église
  - événements, prédications, pages personnalisées et formulaire de contact
- Espace de gestion
  - tableau de bord par rôle
  - gestion des contenus, membres, messages, utilisateurs, invitations, audit et notifications
  - console superadmin pour la gestion des églises, des plans et du cycle de vie tenant

Le modèle métier est centré sur `Church` comme tenant principal. Les accès sont contrôlés par relation utilisateur-église, rôle, statut de l'église et capacités applicatives.

## Stack technique

- Python 3.12+
- Django 5.1+
- PostgreSQL comme base principale
- SQLite comme fallback local si aucune configuration PostgreSQL n'est fournie
- Bootstrap 5
- django-crispy-forms + crispy-bootstrap5
- WhiteNoise pour les fichiers statiques
- Cache Redis optionnel via `CACHE_URL`
- Jobs d'arrière-plan durables en base de données pour les traitements critiques comme l'envoi d'invitations

## Architecture actuelle

### Applications

- `accounts`
  - modèle utilisateur personnalisé
  - configuration Django admin liée aux comptes
- `church`
  - domaine métier principal
  - gestion multi-tenant, contenus, membres, messages, notifications, audit, quotas, invitations et console superadmin

### Configuration du projet

Le projet utilise désormais un package de settings par environnement :

- [base.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/settings/base.py)
- [development.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/settings/development.py)
- [test.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/settings/test.py)
- [production.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/settings/production.py)

Entrées principales :

- [manage.py](c:/Projects/Personal/2026/Full/eglises/manage.py)
- [urls.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/urls.py)
- [wsgi.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/wsgi.py)
- [asgi.py](c:/Projects/Personal/2026/Full/eglises/eglise_saas_project/asgi.py)

### Domaine `church`

Les modèles sont séparés par responsabilité :

- [tenant_models.py](c:/Projects/Personal/2026/Full/eglises/church/tenant_models.py)
  - `Church`
  - `ChurchMembership`
  - `ChurchInvitation`
  - `SiteSettings`
- [content_models.py](c:/Projects/Personal/2026/Full/eglises/church/content_models.py)
  - `Event`
  - `Sermon`
  - `Page`
  - `Member`
- [communication_models.py](c:/Projects/Personal/2026/Full/eglises/church/communication_models.py)
  - `ContactMessage`
  - `ContactMessageReply`
  - `Notification`
  - `AuditLog`
  - `BackgroundJob`

Les vues sont séparées par surface fonctionnelle :

- [views.py](c:/Projects/Personal/2026/Full/eglises/church/views.py)
  - vues dashboard historiques et point d'entrée principal
- [public_views.py](c:/Projects/Personal/2026/Full/eglises/church/public_views.py)
  - site public, invitation, sélection d'église
- [notification_views.py](c:/Projects/Personal/2026/Full/eglises/church/notification_views.py)
  - notifications, audit, paramètres plateforme
- [superadmin_views.py](c:/Projects/Personal/2026/Full/eglises/church/superadmin_views.py)
  - console superadmin
- [view_helpers.py](c:/Projects/Personal/2026/Full/eglises/church/view_helpers.py)
  - helpers partagés de présentation

La logique métier transactionnelle a été extraite dans des services applicatifs :

- [invitation_services.py](c:/Projects/Personal/2026/Full/eglises/church/invitation_services.py)
- [membership_services.py](c:/Projects/Personal/2026/Full/eglises/church/membership_services.py)
- [message_services.py](c:/Projects/Personal/2026/Full/eglises/church/message_services.py)
- [superadmin_services.py](c:/Projects/Personal/2026/Full/eglises/church/superadmin_services.py)

Autres composants importants :

- [permissions.py](c:/Projects/Personal/2026/Full/eglises/church/permissions.py)
  - matrice de capacités et décorateurs d'autorisation
- [limits.py](c:/Projects/Personal/2026/Full/eglises/church/limits.py)
  - calculs de quota, rétention et usage par tenant
- [membership_policy.py](c:/Projects/Personal/2026/Full/eglises/church/membership_policy.py)
  - règles de rattachement utilisateur-église
- [background_jobs.py](c:/Projects/Personal/2026/Full/eglises/church/background_jobs.py)
  - enregistrement et traitement des jobs durables
- [rate_limits.py](c:/Projects/Personal/2026/Full/eglises/church/rate_limits.py)
  - limitation d'abus pour login, contact, invitations
- [middleware.py](c:/Projects/Personal/2026/Full/eglises/church/middleware.py)
  - résolution de l'église courante
- [context_processors.py](c:/Projects/Personal/2026/Full/eglises/church/context_processors.py)
  - injection du contexte tenant et capacités dans les templates

## Rôles et accès

### Superadmin

- gère les paramètres plateforme
- voit tous les audits
- change de contexte d'église
- gère les églises depuis la console plateforme
- attribue les plans et limites
- change le statut tenant : brouillon, active, suspendue, archivée

### Admin d'église

- gère les paramètres de l'église
- gère utilisateurs, memberships et invitations
- gère contenus, membres, messages et audit d'église
- voit l'usage du plan et les limites de son église

### Staff

- gère événements, prédications, pages et membres
- ne gère ni utilisateurs, ni audit, ni paramètres plateforme

### Secrétaire

- gère messages, membres, événements et prédications
- ne gère ni pages, ni utilisateurs, ni audit, ni paramètres plateforme

## Base de données

### Mode recommandé

Le projet est PostgreSQL-first. En pratique :

- si `DATABASE_URL` est défini, Django l'utilise
- sinon, si `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` et `POSTGRES_HOST` sont définis, Django utilise PostgreSQL
- sinon, Django retombe sur SQLite

### Variables de base

Exemple PostgreSQL local :

```env
SECRET_KEY=change-me
DEBUG=True
POSTGRES_DB=eglise_saas
POSTGRES_USER=eglise_user
POSTGRES_PASSWORD=eglise-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
DATABASE_CONN_MAX_AGE=600
DATABASE_SSL_REQUIRE=False
```

Ou avec une URL unique :

```env
DATABASE_URL=postgresql://eglise_user:eglise-password@127.0.0.1:5432/eglise_saas
```

## Installation locale

### 1. Créer et activer l'environnement

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

### 2. Installer les dépendances

```powershell
pip install -r requirements.txt
```

### 3. Configurer `.env`

Créer un fichier `.env` à la racine en s'appuyant sur [`.env.example`](c:/Projects/Personal/2026/Full/eglises/.env.example).

### 4. Démarrer PostgreSQL via Docker

```powershell
docker compose up -d postgres
```

### 5. Appliquer les migrations

```powershell
python manage.py migrate
```

### 6. Lancer le serveur

```powershell
python manage.py runserver
```

## Jobs d'arrière-plan

Les invitations par email et certains traitements critiques passent par des jobs durables stockés en base.

Lancer le worker local :

```powershell
python manage.py process_background_jobs --loop --sleep 5
```

Pour un comportement synchrone en environnement local ciblé, `BACKGROUND_JOBS_EAGER` peut être activé par configuration, mais ce n'est pas le mode normal de production.

## Données de démonstration

Deux options existent selon le besoin :

- [setup_demo.py](c:/Projects/Personal/2026/Full/eglises/church/management/commands/setup_demo.py)
  - crée un environnement de démonstration minimal
- [drc_demo_data.json](c:/Projects/Personal/2026/Full/eglises/church/fixtures/drc_demo_data.json)
  - fixture réaliste en français, orientée RDC

Chargement de la fixture :

```powershell
python manage.py loaddata church/fixtures/drc_demo_data.json
```

## Tests

Le guide de test détaillé se trouve dans [TESTING.md](c:/Projects/Personal/2026/Full/eglises/TESTING.md).

Règle importante :

- utiliser l'environnement virtuel du projet
- ne pas utiliser `py manage.py ...` sur Windows pour ce dépôt

Commandes courantes :

```powershell
.\env\Scripts\Activate.ps1
python manage.py test --noinput
python manage.py check
```

Le projet contient :

- tests unitaires
- tests d'intégration
- tests applicatifs
- tests PostgreSQL ciblés pour les chemins sensibles au verrouillage
- tests navigateur E2E, avec exécution conditionnelle selon l'environnement local

Le dossier principal est [tests](c:/Projects/Personal/2026/Full/eglises/tests).

## Routes principales

### Public

- `/`
- `/login/`
- `/eglise/<slug>/`
- `/eglise/<slug>/evenements/`
- `/eglise/<slug>/predications/`
- `/eglise/<slug>/contact/`
- `/eglise/<slug>/page/<slug>/`
- `/invite/<uuid:token>/`
- `/invitations/`

### Dashboard

- `/dashboard/`
- `/dashboard/selection/`
- `/dashboard/parametres/`
- `/dashboard/evenements/`
- `/dashboard/predications/`
- `/dashboard/membres/`
- `/dashboard/pages/`
- `/dashboard/messages/`
- `/dashboard/notifications/`
- `/dashboard/audit/`
- `/dashboard/utilisateurs/`

### Plateforme superadmin

- `/dashboard/site/`
- `/dashboard/platform/churches/`
- `/dashboard/platform/churches/create/`
- `/dashboard/platform/churches/<id>/`
- `/dashboard/platform/churches/<id>/edit/`
- `/dashboard/platform/churches/<id>/status/`
- `/dashboard/platform/churches/<id>/plan/`

## Déploiement

Le dépôt contient déjà des fichiers de déploiement :

- [render.yaml](c:/Projects/Personal/2026/Full/eglises/render.yaml)
  - web service
  - worker de jobs d'arrière-plan
- [docker-compose.yml](c:/Projects/Personal/2026/Full/eglises/docker-compose.yml)
  - PostgreSQL local pour le développement

En production, utiliser PostgreSQL comme base principale et lancer le worker `process_background_jobs` séparément du processus web.

## Points d'attention actuels

Le projet a déjà une base sérieuse pour la production, mais il faut garder en tête :

- PostgreSQL doit rester la base principale pour les workflows sensibles à la concurrence
- les tests doivent être lancés depuis l'environnement virtuel du projet
- les messages destinés aux utilisateurs restent en français
- les commentaires, docstrings et autres éléments internes de code sont en anglais

## Licence

Projet privé.
