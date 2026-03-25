# Église SaaS

Plateforme SaaS multi-tenant pour les églises, construite avec Django. Chaque église dispose de son site public, de son espace de gestion, de ses utilisateurs, de ses invitations, de ses contenus, de ses messages, de ses notifications et de ses limites de plan.

## Vue d'ensemble

Le projet couvre trois surfaces principales :

- Site public
  - page d'accueil globale avec la liste des églises actives
  - site public propre à chaque église
  - événements, prédications, pages personnalisées et formulaire de contact
- Espace de gestion
  - tableau de bord par rôle
  - gestion des contenus, membres, messages, utilisateurs, invitations, audit et notifications
- Console plateforme
  - gestion des églises, des plans et du cycle de vie tenant

Le modèle métier est centré sur `Church` comme tenant principal. Les accès sont contrôlés par la relation utilisateur-église, le rôle, le statut de l’église et les capacités applicatives.

## Stack technique

- Python 3.12+
- Django 5.1+
- PostgreSQL uniquement
- Bootstrap 5
- `django-crispy-forms` + `crispy-bootstrap5`
- WhiteNoise pour les fichiers statiques
- Cache Redis optionnel via `CACHE_URL`
- Jobs d’arrière-plan durables en base de données pour les traitements critiques comme l’envoi d’invitations et d’emails de contact

## Architecture actuelle

### Applications

- `accounts`
  - modèle utilisateur personnalisé
  - vue de connexion tenant
  - configuration Django admin liée aux comptes
- `church`
  - domaine métier principal
  - gestion multi-tenant, contenus, membres, messages, notifications, audit, quotas, invitations et console superadmin

### Configuration du projet

Le projet utilise un package de settings par environnement :

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

Le domaine est séparé par responsabilité :

- [church/models/tenant.py](c:/Projects/Personal/2026/Full/eglises/church/models/tenant.py)
  - `Church`
  - `ChurchMembership`
  - `ChurchInvitation`
  - `SiteSettings`
- [church/models/content.py](c:/Projects/Personal/2026/Full/eglises/church/models/content.py)
  - `Event`
  - `Sermon`
  - `Page`
  - `Member`
- [church/models/communication.py](c:/Projects/Personal/2026/Full/eglises/church/models/communication.py)
  - `ContactMessage`
  - `ContactMessageReply`
  - `Notification`
  - `AuditLog`
  - `BackgroundJob`

Les vues sont séparées par surface fonctionnelle :

- [accounts/views.py](c:/Projects/Personal/2026/Full/eglises/accounts/views.py)
  - authentification tenant
- [church/views/views.py](c:/Projects/Personal/2026/Full/eglises/church/views/views.py)
  - vues dashboard historiques et point d’entrée principal
- [church/views/public.py](c:/Projects/Personal/2026/Full/eglises/church/views/public.py)
  - site public, invitation, sélection d’église
- [church/views/notification.py](c:/Projects/Personal/2026/Full/eglises/church/views/notification.py)
  - notifications, audit, paramètres plateforme
- [church/views/superadmin.py](c:/Projects/Personal/2026/Full/eglises/church/views/superadmin.py)
  - console superadmin

La logique métier transactionnelle a été extraite dans des services applicatifs :

- [church/services/invitation.py](c:/Projects/Personal/2026/Full/eglises/church/services/invitation.py)
- [church/services/membership.py](c:/Projects/Personal/2026/Full/eglises/church/services/membership.py)
- [church/services/message.py](c:/Projects/Personal/2026/Full/eglises/church/services/message.py)
- [church/services/superadmin.py](c:/Projects/Personal/2026/Full/eglises/church/services/superadmin.py)

Autres composants importants :

- [church/helpers/http.py](c:/Projects/Personal/2026/Full/eglises/church/helpers/http.py)
  - réponses AJAX et parsing des paramètres de requête
- [church/helpers/form.py](c:/Projects/Personal/2026/Full/eglises/church/helpers/form.py)
  - orchestration partagée pour les formulaires CRUD
- [church/helpers/list_view.py](c:/Projects/Personal/2026/Full/eglises/church/helpers/list_view.py)
  - pagination et contexte de listes
- [church/helpers/query.py](c:/Projects/Personal/2026/Full/eglises/church/helpers/query.py)
  - filtres et querysets réutilisables
- [church/helpers/model.py](c:/Projects/Personal/2026/Full/eglises/church/helpers/model.py)
  - fonctions partagées liées aux modèles
- [church/context/church.py](c:/Projects/Personal/2026/Full/eglises/church/context/church.py)
  - résolution de l’église courante et helpers de contexte
- [church/context/processors.py](c:/Projects/Personal/2026/Full/eglises/church/context/processors.py)
  - injection du contexte tenant et des capacités dans les templates
- [church/permissions.py](c:/Projects/Personal/2026/Full/eglises/church/permissions.py)
  - matrice de capacités et décorateurs d’autorisation
- [church/limits.py](c:/Projects/Personal/2026/Full/eglises/church/limits.py)
  - calculs de quota, rétention et usage par tenant
- [church/membership_policy.py](c:/Projects/Personal/2026/Full/eglises/church/membership_policy.py)
  - règles de rattachement utilisateur-église
- [church/background_jobs.py](c:/Projects/Personal/2026/Full/eglises/church/background_jobs.py)
  - enregistrement et traitement des jobs durables
- [church/rate_limits.py](c:/Projects/Personal/2026/Full/eglises/church/rate_limits.py)
  - limitation d’abus pour login, contact et invitations
- [church/middleware.py](c:/Projects/Personal/2026/Full/eglises/church/middleware.py)
  - résolution de l’église courante

## Rôles et accès

### Superadmin

- gère les paramètres plateforme
- voit tous les audits
- change de contexte d’église
- gère les églises depuis la console plateforme
- attribue les plans et limites
- change le statut tenant : brouillon, active, suspendue, archivée

### Admin d’église

- gère les paramètres de l’église
- gère utilisateurs, memberships et invitations
- gère contenus, membres, messages et audit d’église
- voit l’usage du plan et les limites de son église

### Staff

- gère événements, prédications, pages et membres
- ne gère ni utilisateurs, ni audit, ni paramètres plateforme

### Secrétaire

- gère messages, membres, événements et prédications
- ne gère ni pages, ni utilisateurs, ni audit, ni paramètres plateforme

## Base de données

### Mode recommandé

Le projet est PostgreSQL uniquement. En pratique :

- si `DATABASE_URL` est défini, Django l’utilise
- sinon, si `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` et `POSTGRES_HOST` sont définis, Django utilise PostgreSQL
- sinon, le chargement de la configuration lève une erreur explicite

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

### 1. Créer et activer l’environnement

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

### 2. Installer les dépendances

```powershell
pip install -r requirements.txt
```

### 3. Configurer `.env`

Créer un fichier `.env` à la racine en s’appuyant sur [`.env.example`](c:/Projects/Personal/2026/Full/eglises/.env.example).

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

## Jobs d’arrière-plan

Les invitations par email, les emails de contact et certains traitements critiques passent par des jobs durables stockés en base.

Lancer le worker local :

```powershell
python manage.py process_background_jobs --loop --sleep 5
```

Pour un comportement synchrone en environnement local ciblé, `BACKGROUND_JOBS_EAGER` peut être activé par configuration, mais ce n’est pas le mode normal de production.

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

- utiliser l’environnement virtuel du projet
- ne pas utiliser `py manage.py ...` sur Windows pour ce dépôt

Commandes courantes :

```powershell
.\env\Scripts\Activate.ps1
python manage.py test --noinput
python manage.py check
```

Le projet contient :

- tests unitaires
- tests d’intégration
- tests applicatifs
- tests PostgreSQL ciblés pour les chemins sensibles au verrouillage
- tests navigateur E2E, avec exécution conditionnelle selon l’environnement local

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

### Console plateforme

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
  - worker de jobs d’arrière-plan
- [docker-compose.yml](c:/Projects/Personal/2026/Full/eglises/docker-compose.yml)
  - PostgreSQL local pour le développement

En production, utiliser PostgreSQL comme base principale et lancer le worker `process_background_jobs` séparément du processus web.

## Points d’attention actuels

Le projet a déjà une base sérieuse pour la production, mais il faut garder en tête :

- PostgreSQL doit rester la base principale pour les workflows sensibles à la concurrence
- les tests doivent être lancés depuis l’environnement virtuel du projet
- les messages destinés aux utilisateurs restent en français
- les commentaires, docstrings et autres éléments internes de code sont en anglais

## Licence

Projet privé.
