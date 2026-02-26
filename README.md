# ⛪ Église SaaS — Plateforme web dynamique pour églises

Une plateforme Django où **n'importe quelle église** peut avoir son propre site web en le paramétrant simplement (nom, logo, couleurs, horaires, etc.).

---

## 📋 Table des matières

1. [Fonctionnalités](#-fonctionnalités)
2. [Technologies utilisées](#-technologies-utilisées)
3. [Structure du projet](#-structure-du-projet)
4. [Installation pas à pas](#-installation-pas-à-pas)
5. [Lancer l'application](#-lancer-lapplication)
6. [URLs disponibles](#-urls-disponibles)
7. [Guide d'utilisation](#-guide-dutilisation)
8. [Architecture technique](#-architecture-technique)

---

## ✨ Fonctionnalités

### Site public (visiteurs)
- Page d'accueil avec liste de toutes les églises
- Page dédiée par église avec couleurs et logo personnalisés
- Événements à venir
- Prédications (avec liens vidéo/audio)
- Pages dynamiques (À propos, Ministères, etc.)
- Formulaire de contact

### Dashboard administrateur (pasteur/admin)
- Tableau de bord avec statistiques (membres, événements, messages)
- Gestion complète des événements (créer, modifier, supprimer)
- Gestion des prédications
- Gestion des membres
- Lecture des messages de contact
- Paramétrage de l'église (nom, logo, couleurs, horaires, réseaux sociaux)

---

## 🛠 Technologies utilisées

| Technologie | Version | Rôle |
|---|---|---|
| **Python** | 3.13+ | Langage de programmation |
| **Django** | 6.0 | Framework web (gère les routes, la BDD, l'authentification, l'admin) |
| **SQLite** | intégré | Base de données (fichier `db.sqlite3`, aucune installation requise) |
| **Bootstrap 5** | 5.3 | Framework CSS pour un design responsive et professionnel |
| **Bootstrap Icons** | 1.11 | Icônes vectorielles |
| **Pillow** | 12.x | Bibliothèque Python pour le traitement des images (upload logo/photos) |
| **django-crispy-forms** | 2.5 | Rendu élégant des formulaires HTML avec Bootstrap |
| **crispy-bootstrap5** | 2025.x | Template pack Bootstrap 5 pour crispy-forms |

---

## 📁 Structure du projet

```
eglise_saas/
│
├── manage.py                    # Commande principale Django (lancer le serveur, migrations, etc.)
├── requirements.txt             # Liste des dépendances Python
├── db.sqlite3                   # Base de données SQLite (créée automatiquement)
│
├── eglise_saas_project/         # Configuration du projet Django
│   ├── settings.py              # Paramètres globaux (langue FR, fuseau horaire, apps, BDD)
│   ├── urls.py                  # Routes principales (admin, login, logout + inclusion de church/)
│   ├── wsgi.py                  # Point d'entrée pour serveurs de production
│   └── asgi.py                  # Point d'entrée pour serveurs asynchrones
│
├── church/                      # Application principale
│   ├── models.py                # 6 modèles = 6 tables en BDD (Church, Event, Sermon, etc.)
│   ├── views.py                 # Logique de chaque page (20+ vues)
│   ├── urls.py                  # Routes de l'app (URLs publiques + dashboard)
│   ├── forms.py                 # Formulaires auto-générés depuis les modèles
│   ├── admin.py                 # Configuration de l'admin Django
│   ├── context_processors.py    # Injecte l'église courante dans tous les templates
│   └── management/commands/
│       └── setup_demo.py        # Commande pour créer les données de démonstration
│
├── templates/                   # Fichiers HTML
│   ├── base.html                # Template maître (navbar, footer, couleurs dynamiques)
│   ├── registration/
│   │   └── login.html           # Page de connexion
│   ├── church/                  # Pages publiques
│   │   ├── home.html            # Accueil global (liste des églises)
│   │   ├── church_home.html     # Accueil d'une église
│   │   ├── events.html          # Liste des événements
│   │   ├── sermons.html         # Liste des prédications
│   │   ├── contact.html         # Formulaire de contact
│   │   └── custom_page.html     # Pages dynamiques personnalisées
│   └── admin_dashboard/         # Dashboard administrateur
│       ├── base_dashboard.html  # Layout avec sidebar
│       ├── dashboard.html       # Vue d'ensemble + statistiques
│       ├── church_settings.html # Paramètres de l'église
│       ├── manage_events.html   # Liste des événements (CRUD)
│       ├── event_form.html      # Formulaire ajout/modification événement
│       ├── manage_sermons.html  # Liste des prédications (CRUD)
│       ├── sermon_form.html     # Formulaire ajout/modification prédication
│       ├── manage_members.html  # Liste des membres (CRUD)
│       ├── member_form.html     # Formulaire ajout/modification membre
│       ├── manage_messages.html # Liste des messages reçus
│       └── read_message.html    # Lecture d'un message
│
├── static/                      # Fichiers statiques (CSS, JS, images du site)
│   ├── css/
│   ├── js/
│   └── images/
│
├── media/                       # Fichiers uploadés par les utilisateurs (logos, photos)
│
└── venv/                        # Environnement virtuel Python (non versionné)
```

---

## 🚀 Installation pas à pas

### Pré-requis

- **Python 3.10+** installé → vérifier avec `python --version`
- **pip** installé → vérifier avec `pip --version`

### Étape 1 — Cloner ou télécharger le projet

```bash
cd c:\xampp\htdocs
git clone <url-du-repo> eglise_saas
cd eglise_saas
```

Ou si le dossier existe déjà, simplement :
```bash
cd c:\xampp\htdocs\eglise_saas
```

### Étape 2 — Créer l'environnement virtuel

L'environnement virtuel isole les dépendances du projet pour ne pas polluer le Python global.

```bash
python -m venv venv
```

### Étape 3 — Activer l'environnement virtuel

**Windows (PowerShell) :**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD) :**
```cmd
venv\Scripts\activate.bat
```

**Linux / Mac :**
```bash
source venv/bin/activate
```

> Quand l'environnement est activé, vous voyez `(venv)` au début de la ligne de commande.

### Étape 4 — Installer les dépendances

```bash
pip install -r requirements.txt
```

Cela installe :
- `django` — le framework web
- `pillow` — traitement d'images pour les uploads
- `django-crispy-forms` + `crispy-bootstrap5` — formulaires Bootstrap élégants

### Étape 5 — Créer la base de données

Django crée automatiquement les tables à partir des modèles Python :

```bash
python manage.py makemigrations
python manage.py migrate
```

### Étape 6 — Charger les données de démonstration

Cette commande crée un administrateur et une église de test :

```bash
python manage.py setup_demo
```

Elle crée :
- **Utilisateur admin** : `admin` / `admin123`
- **Église de démo** : "Église de la Grâce" (slug: `demo`)
- 3 événements, 3 prédications, 5 membres, 2 pages

---

## ▶ Lancer l'application

### 1. Activer l'environnement virtuel (si pas déjà fait)

```powershell
cd c:\xampp\htdocs\eglise_saas
.\venv\Scripts\Activate.ps1
```

### 2. Lancer le serveur de développement

```bash
python manage.py runserver
```

### 3. Ouvrir dans le navigateur

Le terminal affiche :
```
Starting development server at http://127.0.0.1:8000/
```

Ouvrez cette adresse dans votre navigateur.

### Arrêter le serveur

Appuyez sur `Ctrl + C` dans le terminal.

---

## 🔗 URLs disponibles

| URL | Description | Accès |
|---|---|---|
| `http://localhost:8000/` | Page d'accueil — liste des églises | Public |
| `http://localhost:8000/eglise/demo/` | Site de l'église de démo | Public |
| `http://localhost:8000/eglise/demo/evenements/` | Événements de l'église | Public |
| `http://localhost:8000/eglise/demo/predications/` | Prédications de l'église | Public |
| `http://localhost:8000/eglise/demo/contact/` | Formulaire de contact | Public |
| `http://localhost:8000/eglise/demo/page/a-propos/` | Page "À propos" | Public |
| `http://localhost:8000/login/` | Page de connexion | Public |
| `http://localhost:8000/dashboard/` | Tableau de bord admin | Connecté |
| `http://localhost:8000/dashboard/parametres/` | Paramétrer l'église | Connecté |
| `http://localhost:8000/dashboard/evenements/` | Gérer les événements | Connecté |
| `http://localhost:8000/dashboard/predications/` | Gérer les prédications | Connecté |
| `http://localhost:8000/dashboard/membres/` | Gérer les membres | Connecté |
| `http://localhost:8000/dashboard/messages/` | Voir les messages reçus | Connecté |
| `http://localhost:8000/admin/` | Admin Django (gestion avancée) | Super-admin |

---

## 📖 Guide d'utilisation

### Se connecter
1. Aller sur `http://localhost:8000/login/`
2. Entrer : **admin** / **admin123**
3. Vous êtes redirigé vers le dashboard

### Paramétrer une église
1. Dashboard → **Paramètres**
2. Modifier le nom, logo, couleurs, horaires, réseaux sociaux
3. Cliquer sur **Enregistrer**
4. Le site public se met à jour automatiquement avec les nouvelles couleurs et infos

### Ajouter une nouvelle église
1. Aller sur `http://localhost:8000/admin/`
2. Cliquer sur **Églises** → **Ajouter**
3. Remplir le formulaire (le slug est généré automatiquement)
4. Assigner un utilisateur comme administrateur
5. La nouvelle église est accessible sur `/eglise/<slug>/`

### Créer un nouvel administrateur
```bash
python manage.py createsuperuser
```
Puis dans l'admin Django, associer cet utilisateur à une église.

---

## 🏗 Architecture technique

### Concept multi-église (SaaS)

Chaque église a un **slug unique** (ex: `demo`, `vie-nouvelle`). Ce slug est utilisé dans toutes les URLs :
```
/eglise/<slug>/              → page d'accueil de l'église
/eglise/<slug>/evenements/   → ses événements
/eglise/<slug>/contact/      → son formulaire de contact
```

Les couleurs, le logo et tout le contenu s'adaptent automatiquement grâce au **context processor** qui injecte l'objet `current_church` dans chaque template.

### Base de données — 6 tables

| Table | Description | Lien |
|---|---|---|
| `Church` | Configuration de chaque église | Table centrale |
| `Event` | Événements | → appartient à une Church |
| `Sermon` | Prédications | → appartient à une Church |
| `Member` | Membres | → appartient à une Church |
| `Page` | Pages dynamiques | → appartient à une Church |
| `ContactMessage` | Messages de contact | → appartient à une Church |

### Flux d'une requête

```
Navigateur → URL → urls.py → views.py → models.py (BDD) → template HTML → Réponse
```

1. L'utilisateur tape une URL
2. `urls.py` détermine quelle vue appeler
3. `views.py` récupère les données depuis la base de données via `models.py`
4. La vue envoie ces données à un template HTML
5. Le template génère le HTML final avec Bootstrap 5
6. La réponse est envoyée au navigateur
