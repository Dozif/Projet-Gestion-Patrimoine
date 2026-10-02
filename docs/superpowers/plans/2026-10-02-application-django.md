# Application Django (plan 2/4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire l'application web Django (connexion + double authentification obligatoire, saisie des biens, baux, Pinel, opérations, relevés d'agence, crédit avec import CSV, décomptes de copropriété, déficits, paramètres annuels) et le service qui alimente le moteur `fiscal` depuis la base.

**Architecture:** Projet Django `config/` + applications par domaine (`commun`, `comptes`, `biens`, `operations`, `credit`, `fiscalite`). Vues fonctionnelles et templates serveur au style de la maquette validée. Toutes les pages exigent connexion (`LoginRequiredMiddleware`) puis double authentification TOTP (middleware maison). Montants stockés en centimes (`BigIntegerField`), saisis en euros via `MontantField`. Le service `fiscalite.services.calculer_annee()` convertit la base en dataclasses `fiscal` et appelle le calculateur.

**Tech Stack:** Python 3.14 (venv existant), Django 5.2 LTS, django-otp 1.7 (TOTP), django-axes 8.3, qrcode 8.2, pytest-django 4.14, ruff.

**Spec:** `docs/superpowers/specs/2026-10-02-gestion-patrimoine-design.md` (sections 4, 6, 7). Plan précédent (fusionné) : `docs/superpowers/plans/2026-10-02-moteur-fiscal.md` — API du paquet `fiscal` utilisée telle quelle.

**Hors de ce plan :** tableau de bord chiffré, écran Déclaration, exports, déclaration figée (plan 3) ; Docker, Gunicorn, WhiteNoise, sauvegardes, CI (plan 4).

## Global Constraints

- Montants : entiers en centimes en base (`BigIntegerField`) ; saisie et affichage en euros (`commun.montants`, `MontantField`, filtre `euros`). Jamais de `float`.
- Toute URL exige connexion **et** double authentification, sauf `comptes:connexion`, `comptes:deconnexion`, `comptes:double_authentification` et la page de connexion de l'admin. Aucune vue n'utilise `login_not_required`.
- Les justificatifs ne sont jamais servis par `MEDIA_URL` : uniquement par la vue authentifiée `operations:justificatif`. Pas de `MEDIA_URL` dans les settings.
- Textes visibles en français ; `LANGUAGE_CODE = "fr-fr"`, `TIME_ZONE = "Europe/Paris"`.
- Le paquet `fiscal` reste sans import Django ; seuls les modèles et `fiscalite.services` l'importent.
- Django `>=5.2,<5.3` ; tests `pytest` avec `DJANGO_SETTINGS_MODULE = "config.settings_test"` ; `ruff check --fix .` propre (migrations exclues).
- Commandes depuis `E:/Projet-Gestion-Patrimoine` en Git Bash, Python : `.venv/Scripts/python.exe` (abrégé `PY` ci-dessous ; écrire la commande complète).
- Lignes de plus de 110 caractères signalées par ruff (E501) : les couper sans changer le sens.
- Style : reprendre les jetons de couleur de la maquette (accent `#1F5F5B`, badges recette imposable bleu, déductible vert, non déductible brique, non imposable gris), mode sombre via `prefers-color-scheme`.

## Review Focus

- Accès à une URL sans connexion, ou connecté sans double authentification (y compris `/admin/` et les justificatifs) → redirection vers la connexion ou la double authentification, jamais la page (tests Task 10, Task 7).
- Montant saisi sous des formes françaises variées (`1 234,56`, `1234.56`, `12,5`, `1.234,56`, espace fine, `€`) ou invalide (`abc`, `12,345`) → bon nombre de centimes ou message clair (tests Task 3).
- Fichier CSV de banque en cp1252 ou UTF-8 avec BOM, séparateur `;`, lignes vides, ligne invalide → import correct ou erreur indiquant le numéro de ligne (tests Task 9).
- Modification d'un relevé d'agence ou ré-import d'un échéancier → aucune opération ni échéance en double (tests Task 8, Task 9).
- Paramètres fiscaux de l'année absents → exception explicite `ParametresManquants` nommant l'année, pas une erreur générique (test Task 11).

## File Structure

```text
manage.py
requirements.txt                 # dépendances d'exécution
requirements-dev.txt             # + pytest-django (modifié)
pyproject.toml                   # pytest-django, exclusion migrations (modifié)
README.md                        # lancement local
config/  settings.py settings_test.py urls.py wsgi.py
commun/  montants.py forms.py views.py context_processors.py templatetags/montants.py
comptes/ urls.py views.py middleware.py
biens/   models.py forms.py views.py urls.py admin.py
operations/ models.py forms.py views.py urls.py services.py admin.py migrations/0002_categories.py
credit/  models.py import_csv.py forms.py views.py urls.py
fiscalite/ models.py forms.py views.py urls.py services.py admin.py migrations/0002_parametres.py
           management/commands/seed_demo.py
templates/ base.html base_simple.html accueil.html commun/formulaire.html
           comptes/{connexion,double_authentification}.html
           biens/{liste,detail,pinel,bail}.html operations/liste.html
           credit/{liste,detail,import_fichier,import_colonnes}.html
           fiscalite/{copropriete,deficits}.html
static/css/app.css
tests/conftest.py tests/aides.py tests/{comptes,commun,biens,operations,credit,fiscalite}/…
```

Chaque application contient `__init__.py` (vide), `apps.py` et `migrations/__init__.py` (vide). Modèle d'`apps.py` (remplacer `Biens`/`biens`/libellé) :

```python
from django.apps import AppConfig


class BiensConfig(AppConfig):
    name = "biens"
    verbose_name = "Biens"
```

---

### Task 1: Projet Django, connexion et gabarit

**Files:**
- Create: `requirements.txt`, `manage.py`, `config/__init__.py`, `config/settings.py`, `config/settings_test.py`, `config/urls.py`, `config/wsgi.py`, `commun/{__init__,apps,views,context_processors}.py`, `comptes/{__init__,apps,urls}.py`, `templates/base.html`, `templates/base_simple.html`, `templates/accueil.html`, `templates/comptes/connexion.html`, `static/css/app.css`
- Modify: `requirements-dev.txt`, `pyproject.toml`, `.gitignore`
- Test: `tests/conftest.py`, `tests/comptes/__init__.py`, `tests/comptes/test_connexion.py`

**Interfaces:**
- Produces: URL `accueil` (`/`), `comptes:connexion` (`/compte/connexion/`), `comptes:deconnexion` (POST), `admin:index` ; gabarit `base.html` avec blocs `titre` et `contenu` ; processeur de contexte `navigation` (liste de `{"url","libelle","actif"}`, ignore les URL pas encore définies) ; fixture `utilisateur` (identifiant `proprietaire`, mot de passe `mot-de-passe-solide-123`).

- [ ] **Step 1: Dépendances et configuration des outils**

`requirements.txt` :

```text
Django>=5.2,<5.3
django-otp>=1.7,<2
django-axes>=8.3,<9
qrcode>=8.2,<9
```

`requirements-dev.txt` (remplace le contenu) :

```text
-r requirements.txt
pytest>=8.3
pytest-django>=4.14
ruff>=0.6
```

Dans `pyproject.toml`, section `[tool.pytest.ini_options]`, ajouter la ligne `DJANGO_SETTINGS_MODULE = "config.settings_test"` ; section `[tool.ruff]`, ajouter `extend-exclude = ["*/migrations/*"]`. Ajouter `var/` à `.gitignore`.

Run: `.venv/Scripts/python.exe -m pip install -q -r requirements-dev.txt && .venv/Scripts/python.exe -m django --version`
Expected: `5.2.x`

- [ ] **Step 2: Écrire les tests qui échouent**

`tests/conftest.py` :

```python
import pytest


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user("proprietaire", password="mot-de-passe-solide-123")
```

`tests/comptes/__init__.py` vide. `tests/comptes/test_connexion.py` :

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.urls import reverse

from commun.context_processors import navigation

RACINE = Path(__file__).resolve().parents[2]


@pytest.mark.django_db
def test_accueil_anonyme_redirige_vers_connexion(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.url.startswith(reverse("comptes:connexion"))


@pytest.mark.django_db
def test_page_de_connexion_accessible(client):
    r = client.get(reverse("comptes:connexion"))
    assert r.status_code == 200
    assert "Mot de passe" in r.content.decode()


@pytest.mark.django_db
def test_connexion_reussie_redirige(client, utilisateur):
    r = client.post(
        reverse("comptes:connexion"), {"username": "proprietaire", "password": "mot-de-passe-solide-123"}
    )
    assert r.status_code == 302


def test_production_exige_une_cle_secrete():
    env = {**os.environ, "DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": ""}
    r = subprocess.run(
        [sys.executable, "-c", "import config.settings"], cwd=RACINE, env=env, capture_output=True, text=True
    )
    assert r.returncode != 0
    assert "DJANGO_SECRET_KEY" in r.stderr


def test_navigation_ne_liste_que_les_pages_existantes(rf):
    entrees = navigation(rf.get("/"))["navigation"]
    assert entrees[0] == {"url": "/", "libelle": "Tableau de bord", "actif": True}
    assert {"url": "/admin/", "libelle": "Paramètres", "actif": False} in entrees
```

Run: `.venv/Scripts/python.exe -m pytest tests/comptes -q`
Expected: FAIL (erreur de configuration : module `config` introuvable).

- [ ] **Step 3: Projet Django**

`manage.py` :

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`config/__init__.py` vide. `config/wsgi.py` :

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`config/settings.py` :

```python
"""Réglages de l'application. Les valeurs sensibles viennent des variables d'environnement."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être défini en production.")
    SECRET_KEY = "dev-uniquement-ne-pas-utiliser-en-production"

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

DATA_DIR = Path(os.environ.get("PATRIMOINE_DATA_DIR", BASE_DIR / "var"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "axes",
    "commun",
    "comptes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "commun.context_processors.navigation",
            ],
        },
    },
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "patrimoine.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = DATA_DIR / "static"
# Pas de MEDIA_URL : les justificatifs ne sont servis que par une vue authentifiée.
MEDIA_ROOT = Path(os.environ.get("PATRIMOINE_MEDIA_DIR", DATA_DIR / "justificatifs"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "comptes:connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "comptes:connexion"
SESSION_COOKIE_AGE = 8 * 60 * 60

OTP_TOTP_ISSUER = "Patrimoine"

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # heure
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["username"]

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31_536_000
```

`config/settings_test.py` :

```python
import os
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_DEBUG", "1")

from .settings import *  # noqa: E402, F403

AXES_ENABLED = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="patrimoine-tests-"))
```

`config/urls.py` :

```python
from django.contrib import admin
from django.urls import include, path

from commun.views import accueil

urlpatterns = [
    path("", accueil, name="accueil"),
    path("compte/", include("comptes.urls")),
    path("admin/", admin.site.urls),
]
```

`commun/apps.py` (`CommunConfig`, `name = "commun"`, `verbose_name = "Commun"`) et `comptes/apps.py` (`ComptesConfig`, `name = "comptes"`, `verbose_name = "Comptes"`) selon le modèle de la File Structure ; `commun/__init__.py`, `comptes/__init__.py` vides.

`commun/views.py` :

```python
from django.shortcuts import render


def accueil(request):
    return render(request, "accueil.html")
```

`commun/context_processors.py` :

```python
from django.urls import NoReverseMatch, reverse

ENTREES = (
    ("accueil", "Tableau de bord"),
    ("biens:liste", "Biens"),
    ("operations:liste", "Opérations"),
    ("credit:liste", "Crédit"),
    ("fiscalite:copropriete", "Copropriété"),
    ("fiscalite:deficits", "Déficits"),
    ("admin:index", "Paramètres"),
)


def navigation(request):
    entrees = []
    for nom, libelle in ENTREES:
        try:
            url = reverse(nom)
        except NoReverseMatch:
            continue
        actif = request.path == url if url == "/" else request.path.startswith(url)
        entrees.append({"url": url, "libelle": libelle, "actif": actif})
    return {"navigation": entrees}
```

`comptes/urls.py` :

```python
from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "comptes"

urlpatterns = [
    path(
        "connexion/",
        auth_views.LoginView.as_view(template_name="comptes/connexion.html", redirect_authenticated_user=True),
        name="connexion",
    ),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
]
```

- [ ] **Step 4: Gabarits et feuille de style**

`templates/base.html` :

```html
{% load static %}<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block titre %}Patrimoine{% endblock %} · Patrimoine</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&amp;display=swap">
<link rel="stylesheet" href="{% static 'css/app.css' %}">
</head>
<body>
<div class="shell">
  <aside class="side">
    <a class="marque" href="{% url 'accueil' %}">
      <span class="logo" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/></svg></span>
      <span><strong>Patrimoine</strong><small>Revenus fonciers</small></span>
    </a>
    <nav aria-label="Navigation principale">
      {% for e in navigation %}<a href="{{ e.url }}"{% if e.actif %} class="actif" aria-current="page"{% endif %}>{{ e.libelle }}</a>{% endfor %}
    </nav>
    <form method="post" action="{% url 'comptes:deconnexion' %}" class="compte">
      {% csrf_token %}
      <strong>{{ user.get_username }}</strong>
      <span class="helptext">Double authentification active</span>
      <button type="submit" class="lien">Se déconnecter</button>
    </form>
  </aside>
  <main class="main">
    {% if messages %}<ul class="messages">{% for m in messages %}<li class="message {{ m.tags }}">{{ m }}</li>{% endfor %}</ul>{% endif %}
    {% block contenu %}{% endblock %}
  </main>
</div>
</body>
</html>
```

`templates/base_simple.html` :

```html
{% load static %}<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block titre %}Patrimoine{% endblock %} · Patrimoine</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&amp;display=swap">
<link rel="stylesheet" href="{% static 'css/app.css' %}">
</head>
<body>
<main class="simple">
  <div class="carte">
    {% if messages %}<ul class="messages">{% for m in messages %}<li class="message {{ m.tags }}">{{ m }}</li>{% endfor %}</ul>{% endif %}
    {% block contenu %}{% endblock %}
  </div>
</main>
</body>
</html>
```

`templates/accueil.html` :

```html
{% extends "base.html" %}
{% block titre %}Tableau de bord{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>Tableau de bord</h1><p class="sous-titre">Le tableau de bord chiffré arrive avec la prochaine étape.</p></div></header>
<div class="grille">
  {% for e in navigation %}{% if not forloop.first %}<a class="carte lien-carte" href="{{ e.url }}"><strong>{{ e.libelle }}</strong></a>{% endif %}{% endfor %}
</div>
{% endblock %}
```

`templates/comptes/connexion.html` :

```html
{% extends "base_simple.html" %}
{% block titre %}Connexion{% endblock %}
{% block contenu %}
<h1>Connexion</h1>
<form method="post" class="formulaire">
  {% csrf_token %}
  {{ form }}
  <button class="bouton principal" type="submit">Se connecter</button>
</form>
{% endblock %}
```

`static/css/app.css` :

```css
:root{--fond:#F4F3EF;--cote:#FAF9F6;--surface:#FFFFFF;--encre:#1B1F1E;--attenue:#59605E;--ligne:#E3E1DB;
--accent:#1F5F5B;--accent-doux:#E0EAE9;--accent-encre:#1A514D;
--ri-fond:#E5ECF7;--ri:#1F4475;--ni-fond:#ECECEA;--ni:#474C4A;--d-fond:#E2EFE4;--d:#22552C;--nd-fond:#F7E4E0;--nd:#8A2E22}
@media (prefers-color-scheme:dark){:root{--fond:#131615;--cote:#171A19;--surface:#1C201F;--encre:#ECEEEC;--attenue:#A6ADAA;--ligne:#2D3331;
--accent-doux:#1F3533;--accent-encre:#9CC7C3;--ri-fond:#1E2B3D;--ri:#A9C4EA;--ni-fond:#292D2C;--ni:#C3C8C6;--d-fond:#1C3122;--d:#9FD4A9;--nd-fond:#3A2420;--nd:#F0A99C}}
*{box-sizing:border-box}
body{margin:0;background:var(--fond);color:var(--encre);font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:15px;line-height:1.45;font-variant-numeric:tabular-nums}
a{color:var(--accent-encre)}
h1{margin:0;font-size:28px}
.carte h2{margin:0 0 12px;font-size:17px}
.shell{display:grid;grid-template-columns:232px minmax(0,1fr);min-height:100vh}
.side{background:var(--cote);border-right:1px solid var(--ligne);padding:24px 16px;display:flex;flex-direction:column;gap:28px}
.marque{display:flex;gap:10px;align-items:center;text-decoration:none;color:inherit;padding:0 8px}
.marque .logo{width:36px;height:36px;border-radius:9px;background:var(--accent);display:flex;align-items:center;justify-content:center}
.marque small{display:block;font-size:12px;color:var(--attenue)}
.side nav{display:flex;flex-direction:column;gap:2px}
.side nav a{padding:10px 12px;min-height:44px;border-radius:8px;color:var(--attenue);text-decoration:none;font-weight:500;display:flex;align-items:center}
.side nav a.actif{background:var(--accent-doux);color:var(--accent-encre);font-weight:600}
.compte{margin-top:auto;padding:12px;border:1px solid var(--ligne);border-radius:10px;display:flex;flex-direction:column;gap:4px;font-size:13px}
.main{padding:32px 40px;display:flex;flex-direction:column;gap:24px;min-width:0}
.entete{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;justify-content:space-between}
.sous-titre{color:var(--attenue);margin:4px 0 0}
.carte{background:var(--surface);border:1px solid var(--ligne);border-radius:12px;padding:20px}
.lien-carte{text-decoration:none;color:inherit;min-height:44px}
.grille{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.chiffre{display:block;font-size:24px;font-weight:700;margin-top:6px}
.bouton{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:8px;border:1px solid var(--ligne);background:var(--surface);color:var(--encre);font:inherit;font-weight:600;text-decoration:none;cursor:pointer}
.bouton.principal{background:var(--accent);border-color:var(--accent);color:#FFFFFF}
.bouton.danger{color:var(--nd)}
.lien{background:none;border:none;padding:0;color:var(--accent-encre);font:inherit;cursor:pointer;text-align:left;text-decoration:underline}
.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.tableau{overflow-x:auto;padding:0}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 16px;border-bottom:1px solid var(--ligne);text-align:left;vertical-align:middle}
th{font-size:12px;font-weight:600;color:var(--attenue);text-transform:uppercase;letter-spacing:.04em}
.montant{text-align:right;white-space:nowrap}
.negatif{color:var(--nd)}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px;white-space:nowrap}
.badge.ri{background:var(--ri-fond);color:var(--ri)}
.badge.ni{background:var(--ni-fond);color:var(--ni)}
.badge.d{background:var(--d-fond);color:var(--d)}
.badge.nd{background:var(--nd-fond);color:var(--nd)}
.badge.accent{background:var(--accent-doux);color:var(--accent-encre)}
.puces{display:flex;gap:8px;flex-wrap:wrap}
.puces a{min-height:40px;padding:0 14px;border-radius:999px;border:1px solid var(--ligne);background:var(--surface);color:var(--encre);font-weight:600;font-size:14px;display:inline-flex;align-items:center;text-decoration:none}
.puces a.actif{background:var(--accent);border-color:var(--accent);color:#FFFFFF}
.formulaire{display:flex;flex-direction:column;gap:16px;max-width:680px}
.formulaire>div,.champ{display:flex;flex-direction:column;gap:6px}
label{font-size:13px;font-weight:600;color:var(--attenue)}
input,select,textarea{min-height:44px;padding:8px 12px;border-radius:8px;border:1px solid var(--ligne);background:var(--surface);color:var(--encre);font:inherit}
input[type=checkbox]{min-height:auto;width:20px;height:20px}
.helptext{font-size:12px;color:var(--attenue)}
.errorlist{margin:0;padding:0;list-style:none;color:var(--nd);font-size:13px;font-weight:600}
.messages{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.message{padding:12px 16px;border-radius:10px;background:var(--accent-doux);color:var(--accent-encre);font-weight:600}
.message.error{background:var(--nd-fond);color:var(--nd)}
.filtres{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
dl.infos{display:grid;grid-template-columns:max-content 1fr;gap:8px 16px;margin:0}
dl.infos dt{color:var(--attenue)}
dl.infos dd{margin:0;font-weight:600}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.simple{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px}
.simple .carte{width:100%;max-width:440px;display:flex;flex-direction:column;gap:16px}
.qr svg{width:220px;height:220px;background:#FFFFFF;padding:8px;border-radius:8px}
code.cle{word-break:break-all}
@media (max-width:900px){.shell{grid-template-columns:1fr}.side{border-right:none;border-bottom:1px solid var(--ligne)}.side nav{flex-direction:row;flex-wrap:wrap}.main{padding:20px 16px}}
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `52 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(web): projet Django, connexion et gabarit"
```

---

### Task 2: Double authentification obligatoire (TOTP)

**Files:**
- Create: `comptes/middleware.py`, `comptes/views.py`, `templates/comptes/double_authentification.html`
- Modify: `comptes/urls.py`, `config/settings.py`, `tests/conftest.py`
- Test: `tests/comptes/test_double_authentification.py`

**Interfaces:**
- Consumes: Task 1 (`comptes` URLs, `utilisateur`).
- Produces: URL `comptes:double_authentification` (`/compte/double-authentification/`) ; middleware `comptes.middleware.DoubleAuthentificationObligatoire` ; fixture `client_verifie` (client connecté **et** vérifié OTP), utilisée par toutes les tâches suivantes.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/conftest.py` :

```python
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice


@pytest.fixture
def client_verifie(client, utilisateur):
    appareil = TOTPDevice.objects.create(user=utilisateur, name="test", confirmed=True)
    client.force_login(utilisateur)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = appareil.persistent_id
    session.save()
    return client
```

(placer les imports en tête du fichier.) `tests/comptes/test_double_authentification.py` :

```python
import pytest
from django.conf import settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

pytestmark = pytest.mark.django_db
URL = "/compte/double-authentification/"


def code_pour(appareil):
    return f"{totp(appareil.bin_key, appareil.step, appareil.t0, appareil.digits, appareil.drift):06d}"


def test_connecte_non_verifie_redirige_vers_double_authentification(client, utilisateur):
    client.force_login(utilisateur)
    r = client.get("/")
    assert r.status_code == 302
    assert r.url.startswith(URL)


def test_premiere_fois_affiche_le_qr_code(client, utilisateur):
    client.force_login(utilisateur)
    r = client.get(URL)
    assert r.status_code == 200
    assert "<svg" in r.content.decode()
    assert TOTPDevice.objects.filter(user=utilisateur, confirmed=False).count() == 1


def test_code_valide_confirme_l_appareil_et_donne_acces(client, utilisateur):
    client.force_login(utilisateur)
    client.get(URL)
    appareil = TOTPDevice.objects.get(user=utilisateur)
    r = client.post(URL, {"code": code_pour(appareil)})
    assert r.status_code == 302
    appareil.refresh_from_db()
    assert appareil.confirmed
    assert client.get("/").status_code == 200


def test_code_invalide_affiche_une_erreur(client, utilisateur):
    client.force_login(utilisateur)
    client.get(URL)
    r = client.post(URL, {"code": "abc"})
    assert r.status_code == 200
    assert "Code incorrect" in r.content.decode()


def test_appareil_deja_configure_ne_montre_pas_le_qr(client, utilisateur):
    TOTPDevice.objects.create(user=utilisateur, name="tel", confirmed=True)
    client.force_login(utilisateur)
    contenu = client.get(URL).content.decode()
    assert "<svg" not in contenu
    assert "Saisissez le code à 6 chiffres" in contenu


def test_redirection_externe_refusee(client, utilisateur):
    client.force_login(utilisateur)
    client.get(URL)
    appareil = TOTPDevice.objects.get(user=utilisateur)
    r = client.post(URL + "?next=https://exemple.invalid/", {"code": code_pour(appareil)})
    assert r.url == reverse("accueil")


def test_accueil_accessible_une_fois_verifie(client_verifie):
    r = client_verifie.get("/")
    assert r.status_code == 200
    assert "Tableau de bord" in r.content.decode()


def test_verrouillage_apres_cinq_echecs_par_identifiant():
    assert settings.AXES_FAILURE_LIMIT == 5
    assert settings.AXES_LOCKOUT_PARAMETERS == ["username"]
```

Run: `.venv/Scripts/python.exe -m pytest tests/comptes -q`
Expected: FAIL (la route `/compte/double-authentification/` n'existe pas, l'accueil répond 200 sans vérification).

- [ ] **Step 2: Implémenter**

`comptes/middleware.py` :

```python
from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

CHEMINS_LIBRES = ("comptes:connexion", "comptes:deconnexion", "comptes:double_authentification")


class DoubleAuthentificationObligatoire:
    """Redirige tout utilisateur connecté mais non vérifié par TOTP vers la double authentification."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.is_verified():
            libres = {reverse(nom) for nom in CHEMINS_LIBRES}
            statique = "/" + settings.STATIC_URL.lstrip("/")
            if request.path not in libres and not request.path.startswith(statique):
                cible = reverse("comptes:double_authentification")
                return redirect(f"{cible}?next={quote(request.get_full_path())}")
        return self.get_response(request)
```

Dans `config/settings.py`, insérer `"comptes.middleware.DoubleAuthentificationObligatoire",` dans `MIDDLEWARE` juste après `"django.contrib.auth.middleware.LoginRequiredMiddleware",`.

`comptes/views.py` :

```python
from base64 import b32encode

import qrcode
import qrcode.image.svg
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


def double_authentification(request):
    if request.user.is_verified():
        return redirect("accueil")
    appareil = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    configuration = appareil is None
    if configuration:
        appareil, _ = TOTPDevice.objects.get_or_create(
            user=request.user, confirmed=False, defaults={"name": "Application d'authentification"}
        )
    erreur = None
    if request.method == "POST":
        code = request.POST.get("code", "").replace(" ", "")
        if code.isdigit() and appareil.verify_token(code):
            if configuration:
                appareil.confirmed = True
                appareil.save(update_fields=["confirmed"])
            otp_login(request, appareil)
            suivant = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(
                suivant, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                suivant = reverse("accueil")
            return redirect(suivant)
        erreur = "Code incorrect. Vérifiez l'heure de votre téléphone et réessayez."
    contexte = {"configuration": configuration, "erreur": erreur}
    if configuration:
        image = qrcode.make(appareil.config_url, image_factory=qrcode.image.svg.SvgPathImage)
        contexte["qr_svg"] = image.to_string(encoding="unicode")
        contexte["cle"] = b32encode(appareil.bin_key).decode()
    return render(request, "comptes/double_authentification.html", contexte)
```

Dans `comptes/urls.py`, ajouter `from . import views` et la route :

```python
    path("double-authentification/", views.double_authentification, name="double_authentification"),
```

`templates/comptes/double_authentification.html` :

```html
{% extends "base_simple.html" %}
{% block titre %}Double authentification{% endblock %}
{% block contenu %}
<h1>Double authentification</h1>
{% if configuration %}
<p>Scannez ce QR code avec votre application d'authentification (Google Authenticator, Authy…), puis saisissez le code à 6 chiffres affiché.</p>
<div class="qr">{{ qr_svg|safe }}</div>
<p class="helptext">Impossible de scanner ? Saisissez cette clé : <code class="cle">{{ cle }}</code></p>
{% else %}
<p>Saisissez le code à 6 chiffres affiché par votre application d'authentification.</p>
{% endif %}
{% if erreur %}<p class="errorlist" role="alert">{{ erreur }}</p>{% endif %}
<form method="post" class="formulaire">
  {% csrf_token %}
  <div class="champ">
    <label for="code">Code</label>
    <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required autofocus>
  </div>
  <button class="bouton principal" type="submit">Valider</button>
</form>
<form method="post" action="{% url 'comptes:deconnexion' %}">{% csrf_token %}<button class="lien" type="submit">Se déconnecter</button></form>
{% endblock %}
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `60 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(comptes): double authentification TOTP obligatoire"
```

---

### Task 3: Montants en euros (saisie, affichage)

**Files:**
- Create: `commun/montants.py`, `commun/forms.py`, `commun/templatetags/__init__.py`, `commun/templatetags/montants.py`
- Test: `tests/commun/__init__.py`, `tests/commun/test_montants.py`

**Interfaces:**
- Produces: `parse_euros(texte: str) -> int` (lève `ValueError`), `format_euros(centimes: int) -> str` (espace fine `\u202f` entre milliers, `−` pour le négatif, décimales seulement si non nulles), `centimes_vers_saisie(centimes: int) -> str` ; `MontantField(*, minimum: int | None = 1, valeur_si_vide=None, **kwargs)` (renvoie des centimes) ; filtre de gabarit `{% load montants %}{{ valeur|euros }}` (`—` si `None`).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/commun/test_montants.py` (+ `tests/commun/__init__.py` vide)

```python
import pytest
from django import forms
from django.template import Context, Template

from commun.forms import MontantField
from commun.montants import format_euros, parse_euros


@pytest.mark.parametrize(
    "texte,centimes",
    [("1 234,56", 123456), ("1234.56", 123456), ("12,5", 1250), ("1.234,56", 123456),
     ("1\u202f234,56 €", 123456), ("-5", -500), ("0", 0)],
)
def test_parse_euros(texte, centimes):
    assert parse_euros(texte) == centimes


@pytest.mark.parametrize("texte", ["abc", "12,345", ""])
def test_parse_euros_invalide(texte):
    with pytest.raises(ValueError):
        parse_euros(texte)


@pytest.mark.parametrize(
    "centimes,texte",
    [(744000, "7\u202f440 €"), (4340, "43,40 €"), (-90600, "−906 €"), (0, "0 €"),
     (123456789, "1\u202f234\u202f567,89 €")],
)
def test_format_euros(centimes, texte):
    assert format_euros(centimes) == texte


def test_champ_montant_convertit_en_centimes():
    assert MontantField().clean("1 234,56") == 123456


def test_champ_montant_refuse_zero_par_defaut():
    with pytest.raises(forms.ValidationError, match="supérieur à zéro"):
        MontantField().clean("0")


def test_champ_montant_message_si_invalide():
    with pytest.raises(forms.ValidationError, match="1 234,56"):
        MontantField().clean("abc")


def test_champ_montant_sans_minimum_accepte_negatif():
    assert MontantField(minimum=None).clean("-5") == -500


def test_champ_montant_vide():
    assert MontantField(required=False).clean("") is None
    assert MontantField(required=False, minimum=0, valeur_si_vide=0).clean("") == 0


@pytest.mark.parametrize("centimes,saisie", [(123456, "1234,56"), (-500, "-5,00")])
def test_champ_montant_reaffiche_en_saisie(centimes, saisie):
    assert MontantField().prepare_value(centimes) == saisie


def test_filtre_euros():
    gabarit = Template("{% load montants %}{{ a|euros }}|{{ b|euros }}")
    assert gabarit.render(Context({"a": 4340, "b": None})) == "43,40 €|—"
```

Run: `.venv/Scripts/python.exe -m pytest tests/commun -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'commun.forms'`.

- [ ] **Step 2: Implémenter**

`commun/montants.py` :

```python
"""Conversion entre saisie en euros et centimes entiers."""

import re
from decimal import Decimal

ESPACE_FINE = "\u202f"
_MONTANT = re.compile(r"-?\d+(\.\d{1,2})?")


def parse_euros(texte: str) -> int:
    """'1 234,56 €' -> 123456. Lève ValueError si le texte n'est pas un montant."""
    propre = texte
    for caractere in (" ", "\u00a0", ESPACE_FINE, "€"):
        propre = propre.replace(caractere, "")
    propre = propre.replace("−", "-").strip()
    if propre.count(",") == 1 and "." in propre:
        propre = propre.replace(".", "")
    propre = propre.replace(",", ".")
    if not _MONTANT.fullmatch(propre):
        raise ValueError(f"Montant invalide : {texte!r}")
    return int(Decimal(propre) * 100)


def format_euros(centimes: int) -> str:
    signe = "−" if centimes < 0 else ""
    euros, cts = divmod(abs(centimes), 100)
    groupes = f"{euros:,}".replace(",", ESPACE_FINE)
    return f"{signe}{groupes},{cts:02d} €" if cts else f"{signe}{groupes} €"


def centimes_vers_saisie(centimes: int) -> str:
    signe = "-" if centimes < 0 else ""
    euros, cts = divmod(abs(centimes), 100)
    return f"{signe}{euros},{cts:02d}"
```

`commun/forms.py` :

```python
from django import forms

from .montants import centimes_vers_saisie, format_euros, parse_euros


class MontantField(forms.CharField):
    """Champ de saisie en euros ; `cleaned_data` contient des centimes."""

    def __init__(self, *, minimum: int | None = 1, valeur_si_vide=None, **kwargs):
        self.minimum = minimum
        self.valeur_si_vide = valeur_si_vide
        kwargs.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}))
        super().__init__(**kwargs)

    def prepare_value(self, value):
        if isinstance(value, int) and not isinstance(value, bool):
            return centimes_vers_saisie(value)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return self.valeur_si_vide
        try:
            centimes = parse_euros(value)
        except ValueError:
            raise forms.ValidationError(
                "Saisissez un montant en euros, par exemple 1 234,56.", code="invalide"
            ) from None
        if self.minimum is not None and centimes < self.minimum:
            if self.minimum == 1:
                raise forms.ValidationError("Le montant doit être supérieur à zéro.", code="minimum")
            raise forms.ValidationError(
                f"Le montant doit être au moins {format_euros(self.minimum)}.", code="minimum"
            )
        return centimes
```

`commun/templatetags/__init__.py` vide. `commun/templatetags/montants.py` :

```python
from django import template

from commun.montants import format_euros

register = template.Library()


@register.filter
def euros(centimes):
    return "—" if centimes is None else format_euros(centimes)
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `83 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(commun): saisie et affichage des montants en euros"
```

---

### Task 4: Modèles des biens, baux et Pinel

**Files:**
- Create: `biens/{__init__,apps,models,admin}.py`, `biens/migrations/__init__.py`, `biens/migrations/0001_initial.py` (générée)
- Modify: `config/settings.py` (ajouter `"biens",` à la fin d'`INSTALLED_APPS`)
- Test: `tests/aides.py`, `tests/biens/__init__.py`, `tests/biens/test_modeles.py`

**Interfaces:**
- Consumes: `fiscal.Bien`, `fiscal.EngagementPinel`, `fiscal.PeriodePinel`.
- Produces: modèles `Bien` (`nom`, `adresse`, `surface_habitable`, `surface_annexes`, `date_acquisition`, `prix_revient`, `regime`, `nb_locaux`, `actif` ; `vers_fiscal() -> fiscal.Bien` ; `bail_en_cours(jour) -> Bail | None` ; `get_absolute_url()` → `biens:detail`), `RegimeFiscal`, `EngagementPinel` (OneToOne `bien.pinel` ; `vers_fiscal()`), `PeriodePinel` (`engagement.periodes`), `Locataire`, `Bail` (`bien.baux`). Aide de test `creer_bien(nom="T2 Les Tilleuls", **kw) -> Bien`.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/aides.py` :

```python
from decimal import Decimal

from biens.models import Bien


def creer_bien(nom="T2 Les Tilleuls", **kw):
    kw.setdefault("surface_habitable", Decimal("45"))
    kw.setdefault("prix_revient", 16_800_000)
    return Bien.objects.create(nom=nom, **kw)
```

`tests/biens/__init__.py` vide. `tests/biens/test_modeles.py` :

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

import fiscal
from biens.models import Bail, Bien, EngagementPinel, Locataire, PeriodePinel
from fiscal.pinel import reduction_annee
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def test_bien_vers_fiscal():
    b = creer_bien(nb_locaux=2)
    assert b.vers_fiscal() == fiscal.Bien(id=b.pk, nom="T2 Les Tilleuls", regime="FONCIER_REEL", nb_locaux=2)


def test_engagement_pinel_vers_fiscal_calcule_la_reduction():
    e = EngagementPinel.objects.create(
        bien=creer_bien(), date_mise_en_location=date(2015, 1, 1), duree_annees=12, zone="A",
        prix_revient=16_800_000, surface_habitable=Decimal("45"),
    )
    PeriodePinel.objects.create(engagement=e, annee_debut=2015, annee_fin=2023, taux_annuel=Decimal("2"))
    PeriodePinel.objects.create(engagement=e, annee_debut=2024, annee_fin=2026, taux_annuel=Decimal("1"))
    assert reduction_annee(e.vers_fiscal(), 2026) == 168_000


def test_bail_en_cours():
    b = creer_bien()
    loc = Locataire.objects.create(nom="Locataire")
    ancien = Bail.objects.create(
        bien=b, locataire=loc, date_debut=date(2020, 1, 1), date_fin=date(2023, 6, 30), loyer_hc=60_000
    )
    actuel = Bail.objects.create(bien=b, locataire=loc, date_debut=date(2023, 7, 1), loyer_hc=62_000)
    assert b.bail_en_cours(date(2025, 1, 1)) == actuel
    assert b.bail_en_cours(date(2021, 1, 1)) == ancien
    assert b.bail_en_cours(date(2019, 1, 1)) is None


def test_bail_qui_finit_avant_de_commencer_refuse():
    bail = Bail(
        bien=creer_bien(), locataire=Locataire.objects.create(nom="L"), date_debut=date(2024, 1, 1),
        date_fin=date(2023, 1, 1), loyer_hc=1,
    )
    with pytest.raises(ValidationError):
        bail.full_clean()


def test_bien_sans_local_refuse():
    with pytest.raises(ValidationError):
        Bien(nom="X", surface_habitable=Decimal("10"), nb_locaux=0).full_clean()
```

Run: `.venv/Scripts/python.exe -m pytest tests/biens -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'biens'`.

- [ ] **Step 2: Implémenter** — `biens/apps.py` (`BiensConfig`), `biens/__init__.py` et `biens/migrations/__init__.py` vides, puis `biens/models.py` :

```python
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

import fiscal


class RegimeFiscal(models.TextChoices):
    FONCIER_REEL = "FONCIER_REEL", "Location vide — régime réel"


class Bien(models.Model):
    nom = models.CharField("nom", max_length=100, unique=True)
    adresse = models.TextField("adresse", blank=True)
    surface_habitable = models.DecimalField("surface habitable (m²)", max_digits=6, decimal_places=2)
    surface_annexes = models.DecimalField("surface des annexes (m²)", max_digits=6, decimal_places=2, default=0)
    date_acquisition = models.DateField("date d'acquisition", null=True, blank=True)
    prix_revient = models.BigIntegerField("prix de revient (centimes)", default=0)
    regime = models.CharField(
        "régime fiscal", max_length=30, choices=RegimeFiscal.choices, default=RegimeFiscal.FONCIER_REEL
    )
    nb_locaux = models.PositiveSmallIntegerField("nombre de locaux", default=1, validators=[MinValueValidator(1)])
    actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse("biens:detail", args=[self.pk])

    def vers_fiscal(self) -> fiscal.Bien:
        return fiscal.Bien(id=self.pk, nom=self.nom, regime=self.regime, nb_locaux=self.nb_locaux)

    def bail_en_cours(self, jour):
        return (
            self.baux.filter(date_debut__lte=jour)
            .filter(models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=jour))
            .order_by("-date_debut")
            .first()
        )


class EngagementPinel(models.Model):
    ZONES = [("A bis", "A bis"), ("A", "A"), ("B1", "B1"), ("B2", "B2"), ("C", "C")]

    bien = models.OneToOneField(Bien, on_delete=models.CASCADE, related_name="pinel")
    date_mise_en_location = models.DateField("date de mise en location")
    duree_annees = models.PositiveSmallIntegerField(
        "durée de l'engagement", choices=[(6, "6 ans"), (9, "9 ans"), (12, "12 ans")]
    )
    zone = models.CharField("zone", max_length=10, choices=ZONES)
    prix_revient = models.BigIntegerField("prix de revient retenu (centimes)")
    surface_habitable = models.DecimalField("surface habitable retenue (m²)", max_digits=6, decimal_places=2)

    def __str__(self):
        return f"Pinel — {self.bien}"

    def vers_fiscal(self) -> fiscal.EngagementPinel:
        return fiscal.EngagementPinel(
            self.date_mise_en_location, self.duree_annees, self.prix_revient, self.surface_habitable,
            tuple(p.vers_fiscal() for p in self.periodes.all()),
        )


class PeriodePinel(models.Model):
    engagement = models.ForeignKey(EngagementPinel, on_delete=models.CASCADE, related_name="periodes")
    annee_debut = models.PositiveSmallIntegerField("année de début")
    annee_fin = models.PositiveSmallIntegerField("année de fin")
    taux_annuel = models.DecimalField("taux annuel (%)", max_digits=4, decimal_places=2)

    class Meta:
        ordering = ["annee_debut"]

    def vers_fiscal(self) -> fiscal.PeriodePinel:
        return fiscal.PeriodePinel(self.annee_debut, self.annee_fin, self.taux_annuel)


class Locataire(models.Model):
    nom = models.CharField("nom", max_length=150)
    email = models.EmailField("e-mail", blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    revenu_fiscal_reference = models.BigIntegerField(
        "revenu fiscal de référence à la signature (centimes)", null=True, blank=True
    )
    nb_personnes_foyer = models.PositiveSmallIntegerField("personnes dans le foyer", null=True, blank=True)

    def __str__(self):
        return self.nom


class Bail(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="baux")
    locataire = models.ForeignKey(Locataire, on_delete=models.PROTECT, related_name="baux")
    date_debut = models.DateField("début")
    date_fin = models.DateField("fin", null=True, blank=True)
    loyer_hc = models.BigIntegerField("loyer mensuel hors charges (centimes)")
    provision_charges = models.BigIntegerField("provision mensuelle sur charges (centimes)", default=0)
    depot_garantie = models.BigIntegerField("dépôt de garantie (centimes)", default=0)

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.bien} — {self.locataire}"

    def clean(self):
        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La fin du bail doit être postérieure à son début."})
```

`biens/admin.py` :

```python
from django.contrib import admin

from .models import Locataire

admin.site.register(Locataire)
```

Ajouter `"biens",` à la fin d'`INSTALLED_APPS`.

Run: `DJANGO_DEBUG=1 .venv/Scripts/python.exe manage.py makemigrations biens`
Expected: `Migrations for 'biens': biens/migrations/0001_initial.py`

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `88 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(biens): modèles biens, baux, locataires et Pinel"
```

---

### Task 5: Écrans des biens (liste, fiche, Pinel, bail)

**Files:**
- Create: `biens/forms.py`, `biens/views.py`, `biens/urls.py`, `templates/commun/formulaire.html`, `templates/biens/{liste,detail,pinel,bail}.html`
- Modify: `config/urls.py` (ajouter `path("biens/", include("biens.urls")),`)
- Test: `tests/biens/test_vues.py`

**Interfaces:**
- Consumes: Task 3 (`MontantField`, filtre `euros`), Task 4 (modèles), `fiscal.pinel`.
- Produces: URLs `biens:liste` (`/biens/`), `biens:creer` (`/biens/nouveau/`), `biens:detail`, `biens:modifier`, `biens:pinel`, `biens:creer_bail`, `biens:modifier_bail` ; gabarit générique `commun/formulaire.html` (contexte : `form`, `titre`, `intro`, `retour`, `suppression`).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/biens/test_vues.py`

```python
import pytest
from django.urls import reverse

from biens.models import Bail, Bien, EngagementPinel
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def donnees_pinel(periodes):
    d = {
        "date_mise_en_location": "2015-01-01", "duree_annees": "12", "zone": "A",
        "prix_revient": "168 000", "surface_habitable": "45",
        "periodes-TOTAL_FORMS": str(len(periodes)), "periodes-INITIAL_FORMS": "0",
        "periodes-MIN_NUM_FORMS": "0", "periodes-MAX_NUM_FORMS": "1000",
    }
    for i, (debut, fin, taux) in enumerate(periodes):
        d[f"periodes-{i}-annee_debut"] = str(debut)
        d[f"periodes-{i}-annee_fin"] = str(fin)
        d[f"periodes-{i}-taux_annuel"] = str(taux)
    return d


def test_creation_d_un_bien_avec_prix_en_euros(client_verifie):
    r = client_verifie.post(reverse("biens:creer"), {
        "nom": "T2 Les Tilleuls", "surface_habitable": "45", "surface_annexes": "7",
        "prix_revient": "168 000", "regime": "FONCIER_REEL", "nb_locaux": "1", "actif": "on",
    })
    assert r.status_code == 302
    assert Bien.objects.get().prix_revient == 16_800_000


def test_fiche_affiche_le_prix_formate(client_verifie):
    b = creer_bien()
    assert "168\u202f000 €" in client_verifie.get(b.get_absolute_url()).content.decode()


def test_liste_des_biens(client_verifie):
    creer_bien("T3 Centre")
    assert "T3 Centre" in client_verifie.get(reverse("biens:liste")).content.decode()


def test_periodes_pinel_qui_se_chevauchent_refusees(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("biens:pinel", args=[b.pk]), donnees_pinel([(2015, 2023, 2), (2023, 2026, 1)]))
    assert r.status_code == 200
    assert "chevauchent" in r.content.decode()
    assert not EngagementPinel.objects.exists()


def test_engagement_pinel_valide_enregistre(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("biens:pinel", args=[b.pk]), donnees_pinel([(2015, 2023, 2), (2024, 2026, 1)]))
    assert r.status_code == 302
    assert EngagementPinel.objects.get(bien=b).periodes.count() == 2


def test_creation_d_un_bail_avec_son_locataire(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("biens:creer_bail", args=[b.pk]), {
        "locataire-nom": "Locataire A", "bail-date_debut": "2023-09-01", "bail-loyer_hc": "620",
        "bail-provision_charges": "40", "bail-depot_garantie": "",
    })
    assert r.status_code == 302
    bail = Bail.objects.get()
    assert (bail.loyer_hc, bail.provision_charges, bail.depot_garantie) == (62_000, 4_000, 0)
    assert bail.locataire.nom == "Locataire A"


def test_bien_inexistant(client_verifie):
    assert client_verifie.get(reverse("biens:detail", args=[999])).status_code == 404
```

Run: `.venv/Scripts/python.exe -m pytest tests/biens/test_vues.py -q`
Expected: FAIL (`NoReverseMatch: 'biens' is not a registered namespace`).

- [ ] **Step 2: Formulaires** — `biens/forms.py`

```python
from django import forms
from django.forms import inlineformset_factory

import fiscal
from commun.forms import MontantField

from .models import Bail, Bien, EngagementPinel, Locataire, PeriodePinel

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class BienForm(forms.ModelForm):
    prix_revient = MontantField(label="Prix de revient (€)", help_text="Prix d'achat et frais d'acquisition.")

    class Meta:
        model = Bien
        fields = [
            "nom", "adresse", "surface_habitable", "surface_annexes", "date_acquisition", "prix_revient",
            "regime", "nb_locaux", "actif",
        ]
        widgets = {"date_acquisition": DATE, "adresse": forms.Textarea(attrs={"rows": 2})}


class EngagementPinelForm(forms.ModelForm):
    prix_revient = MontantField(label="Prix de revient retenu (€)")

    class Meta:
        model = EngagementPinel
        fields = ["date_mise_en_location", "duree_annees", "zone", "prix_revient", "surface_habitable"]
        widgets = {"date_mise_en_location": DATE}


PeriodeFormSet = inlineformset_factory(
    EngagementPinel, PeriodePinel, fields=["annee_debut", "annee_fin", "taux_annuel"], extra=2, can_delete=True,
    widgets={
        "annee_debut": forms.NumberInput(attrs={"aria-label": "Année de début"}),
        "annee_fin": forms.NumberInput(attrs={"aria-label": "Année de fin"}),
        "taux_annuel": forms.NumberInput(attrs={"aria-label": "Taux annuel en %", "step": "0.01"}),
    },
)


def verifier_engagement(form, formset) -> str | None:
    """Contrôle la cohérence du calendrier avec le moteur fiscal ; renvoie le message d'erreur éventuel."""
    periodes = tuple(
        fiscal.PeriodePinel(f.cleaned_data["annee_debut"], f.cleaned_data["annee_fin"], f.cleaned_data["taux_annuel"])
        for f in formset.forms
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    )
    d = form.cleaned_data
    try:
        fiscal.EngagementPinel(
            d["date_mise_en_location"], d["duree_annees"], d["prix_revient"], d["surface_habitable"], periodes
        )
    except ValueError as erreur:
        return str(erreur)
    return None


class LocataireForm(forms.ModelForm):
    revenu_fiscal_reference = MontantField(label="Revenu fiscal de référence à la signature (€)", required=False)

    class Meta:
        model = Locataire
        fields = ["nom", "email", "telephone", "revenu_fiscal_reference", "nb_personnes_foyer"]


class BailForm(forms.ModelForm):
    loyer_hc = MontantField(label="Loyer mensuel hors charges (€)")
    provision_charges = MontantField(
        label="Provision mensuelle sur charges (€)", required=False, minimum=0, valeur_si_vide=0
    )
    depot_garantie = MontantField(label="Dépôt de garantie (€)", required=False, minimum=0, valeur_si_vide=0)

    class Meta:
        model = Bail
        fields = ["date_debut", "date_fin", "loyer_hc", "provision_charges", "depot_garantie"]
        widgets = {"date_debut": DATE, "date_fin": DATE}
```

- [ ] **Step 3: Vues et routes**

`biens/views.py` :

```python
from datetime import date

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from fiscal.pinel import fin_engagement, reduction_annee, reduction_cumulee, reduction_totale

from .forms import BailForm, BienForm, EngagementPinelForm, LocataireForm, PeriodeFormSet, verifier_engagement
from .models import Bail, Bien, EngagementPinel, Locataire


def liste(request):
    return render(request, "biens/liste.html", {"biens": Bien.objects.all()})


def creer(request):
    return _formulaire_bien(request, Bien())


def modifier(request, pk):
    return _formulaire_bien(request, get_object_or_404(Bien, pk=pk))


def _formulaire_bien(request, bien):
    form = BienForm(request.POST or None, instance=bien)
    if request.method == "POST" and form.is_valid():
        bien = form.save()
        messages.success(request, f"Bien « {bien.nom} » enregistré.")
        return redirect(bien)
    titre = "Modifier le bien" if bien.pk else "Nouveau bien"
    return render(request, "commun/formulaire.html", {"form": form, "titre": titre, "retour": reverse("biens:liste")})


def detail(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    pinel = getattr(bien, "pinel", None)
    aujourd_hui = date.today()
    contexte = {
        "bien": bien,
        "bail": bien.bail_en_cours(aujourd_hui),
        "baux": bien.baux.select_related("locataire"),
        "pinel": pinel,
    }
    if pinel is not None:
        engagement = pinel.vers_fiscal()
        contexte.update(
            annee=aujourd_hui.year,
            reduction_annee=reduction_annee(engagement, aujourd_hui.year),
            reduction_cumulee=reduction_cumulee(engagement, aujourd_hui.year),
            reduction_totale=reduction_totale(engagement),
            fin_engagement=fin_engagement(engagement),
        )
    return render(request, "biens/detail.html", contexte)


def pinel(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    engagement = getattr(bien, "pinel", None) or EngagementPinel(bien=bien)
    form = EngagementPinelForm(request.POST or None, instance=engagement)
    formset = PeriodeFormSet(request.POST or None, instance=engagement, prefix="periodes")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        erreur = verifier_engagement(form, formset)
        if erreur:
            form.add_error(None, erreur)
        else:
            with transaction.atomic():
                engagement = form.save()
                formset.instance = engagement
                formset.save()
            messages.success(request, "Engagement Pinel enregistré.")
            return redirect(bien)
    return render(request, "biens/pinel.html", {"bien": bien, "form": form, "formset": formset})


def creer_bail(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    return _formulaire_bail(request, bien, Bail(bien=bien))


def modifier_bail(request, pk, bail_pk):
    bien = get_object_or_404(Bien, pk=pk)
    return _formulaire_bail(request, bien, get_object_or_404(Bail, pk=bail_pk, bien=bien))


def _formulaire_bail(request, bien, bail):
    locataire = bail.locataire if bail.pk else Locataire()
    form_locataire = LocataireForm(request.POST or None, instance=locataire, prefix="locataire")
    form_bail = BailForm(request.POST or None, instance=bail, prefix="bail")
    if request.method == "POST" and form_locataire.is_valid() and form_bail.is_valid():
        with transaction.atomic():
            bail = form_bail.save(commit=False)
            bail.bien = bien
            bail.locataire = form_locataire.save()
            bail.save()
        messages.success(request, "Bail enregistré.")
        return redirect(bien)
    return render(
        request, "biens/bail.html",
        {"bien": bien, "bail": bail, "form_locataire": form_locataire, "form_bail": form_bail},
    )
```

`biens/urls.py` :

```python
from django.urls import path

from . import views

app_name = "biens"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/pinel/", views.pinel, name="pinel"),
    path("<int:pk>/baux/nouveau/", views.creer_bail, name="creer_bail"),
    path("<int:pk>/baux/<int:bail_pk>/", views.modifier_bail, name="modifier_bail"),
]
```

Dans `config/urls.py`, ajouter `path("biens/", include("biens.urls")),` après la ligne `compte/`.

- [ ] **Step 4: Gabarits**

`templates/commun/formulaire.html` :

```html
{% extends "base.html" %}
{% block titre %}{{ titre }}{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>{{ titre }}</h1>{% if intro %}<p class="sous-titre">{{ intro }}</p>{% endif %}</div></header>
<form method="post" enctype="multipart/form-data" class="carte formulaire">
  {% csrf_token %}
  {{ form }}
  <div class="actions">
    <button type="submit" class="bouton principal">Enregistrer</button>
    {% if retour %}<a class="bouton" href="{{ retour }}">Annuler</a>{% endif %}
  </div>
</form>
{% if suppression %}
<form method="post" action="{{ suppression }}">{% csrf_token %}<button type="submit" class="bouton danger">Supprimer</button></form>
{% endif %}
{% endblock %}
```

`templates/biens/liste.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Biens{% endblock %}
{% block contenu %}
<header class="entete">
  <div><h1>Biens</h1><p class="sous-titre">{{ biens|length }} bien{{ biens|length|pluralize }}</p></div>
  <a class="bouton principal" href="{% url 'biens:creer' %}">+ Nouveau bien</a>
</header>
<div class="carte tableau">
<table>
  <thead><tr><th>Nom</th><th>Régime</th><th class="montant">Surface</th><th class="montant">Prix de revient</th><th>Dispositif</th></tr></thead>
  <tbody>
  {% for bien in biens %}
    <tr>
      <td><a href="{{ bien.get_absolute_url }}">{{ bien.nom }}</a></td>
      <td>{{ bien.get_regime_display }}</td>
      <td class="montant">{{ bien.surface_habitable }} m²</td>
      <td class="montant">{{ bien.prix_revient|euros }}</td>
      <td>{% if bien.pinel %}<span class="badge accent">Pinel</span>{% else %}—{% endif %}</td>
    </tr>
  {% empty %}
    <tr><td colspan="5">Aucun bien pour l'instant.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
```

`templates/biens/detail.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}{{ bien.nom }}{% endblock %}
{% block contenu %}
<header class="entete">
  <div><h1>{{ bien.nom }}</h1><p class="sous-titre">{{ bien.get_regime_display }}{% if bien.adresse %} · {{ bien.adresse }}{% endif %}</p></div>
  <a class="bouton" href="{% url 'biens:modifier' bien.pk %}">Modifier</a>
</header>
<div class="grille">
  <section class="carte">
    <h2>Informations</h2>
    <dl class="infos">
      <dt>Surface habitable</dt><dd>{{ bien.surface_habitable }} m²</dd>
      <dt>Annexes</dt><dd>{{ bien.surface_annexes }} m²</dd>
      <dt>Acquisition</dt><dd>{{ bien.date_acquisition|default:"—" }}</dd>
      <dt>Prix de revient</dt><dd>{{ bien.prix_revient|euros }}</dd>
      <dt>Locaux</dt><dd>{{ bien.nb_locaux }}</dd>
    </dl>
  </section>
  <section class="carte">
    <h2>Bail en cours</h2>
    {% if bail %}
    <dl class="infos">
      <dt>Locataire</dt><dd>{{ bail.locataire.nom }}</dd>
      <dt>Depuis</dt><dd>{{ bail.date_debut }}</dd>
      <dt>Loyer HC</dt><dd>{{ bail.loyer_hc|euros }}</dd>
      <dt>Provision charges</dt><dd>{{ bail.provision_charges|euros }}</dd>
    </dl>
    <p><a href="{% url 'biens:modifier_bail' bien.pk bail.pk %}">Modifier le bail</a></p>
    {% else %}<p>Aucun bail en cours.</p>{% endif %}
    <p><a class="bouton" href="{% url 'biens:creer_bail' bien.pk %}">+ Nouveau bail</a></p>
    {% if baux|length > 1 %}
    <h3>Historique</h3>
    <ul>{% for b in baux %}<li><a href="{% url 'biens:modifier_bail' bien.pk b.pk %}">{{ b.locataire.nom }}</a> — {{ b.date_debut }} → {{ b.date_fin|default:"en cours" }} — {{ b.loyer_hc|euros }}</li>{% endfor %}</ul>
    {% endif %}
  </section>
  <section class="carte">
    <h2>Pinel</h2>
    {% if pinel %}
    <dl class="infos">
      <dt>Zone</dt><dd>{{ pinel.zone }}</dd>
      <dt>Engagement</dt><dd>{{ pinel.duree_annees }} ans, fin le {{ fin_engagement }}</dd>
      <dt>Réduction {{ annee }}</dt><dd>{{ reduction_annee|euros }}</dd>
      <dt>Cumul obtenu</dt><dd>{{ reduction_cumulee|euros }} sur {{ reduction_totale|euros }}</dd>
    </dl>
    <p><a href="{% url 'biens:pinel' bien.pk %}">Modifier l'engagement</a></p>
    {% else %}
    <p>Pas d'engagement Pinel.</p>
    <p><a class="bouton" href="{% url 'biens:pinel' bien.pk %}">Ajouter un engagement Pinel</a></p>
    {% endif %}
  </section>
</div>
{% endblock %}
```

`templates/biens/pinel.html` :

```html
{% extends "base.html" %}
{% block titre %}Pinel — {{ bien.nom }}{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>Engagement Pinel</h1><p class="sous-titre">{{ bien.nom }}</p></div></header>
<form method="post" class="carte formulaire">
  {% csrf_token %}
  {{ form }}
  <h2>Calendrier de réduction</h2>
  <p class="helptext">Une ligne par période, par exemple 2 % par an de 2015 à 2023 puis 1 % par an de 2024 à 2026. Reprenez les taux de vos avis d'imposition.</p>
  {{ formset.management_form }}
  {{ formset.non_form_errors }}
  <table>
    <thead><tr><th>Année de début</th><th>Année de fin</th><th>Taux annuel (%)</th><th>Supprimer</th></tr></thead>
    <tbody>
    {% for f in formset %}
      <tr>
        {% for cache in f.hidden_fields %}{{ cache }}{% endfor %}
        <td>{{ f.annee_debut }}{{ f.annee_debut.errors }}</td>
        <td>{{ f.annee_fin }}{{ f.annee_fin.errors }}</td>
        <td>{{ f.taux_annuel }}{{ f.taux_annuel.errors }}</td>
        <td>{% if f.instance.pk %}{{ f.DELETE }}{% endif %}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  <div class="actions">
    <button class="bouton principal" type="submit">Enregistrer</button>
    <a class="bouton" href="{{ bien.get_absolute_url }}">Annuler</a>
  </div>
</form>
{% endblock %}
```

`templates/biens/bail.html` :

```html
{% extends "base.html" %}
{% block titre %}Bail — {{ bien.nom }}{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>{% if bail.pk %}Modifier le bail{% else %}Nouveau bail{% endif %}</h1><p class="sous-titre">{{ bien.nom }}</p></div></header>
<form method="post" class="carte formulaire">
  {% csrf_token %}
  <h2>Locataire</h2>
  {{ form_locataire }}
  <h2>Bail</h2>
  {{ form_bail }}
  <div class="actions">
    <button class="bouton principal" type="submit">Enregistrer</button>
    <a class="bouton" href="{{ bien.get_absolute_url }}">Annuler</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `95 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(biens): écrans des biens, baux et engagement Pinel"
```

---

### Task 6: Catégories, opérations et relevés d'agence (modèles)

**Files:**
- Create: `operations/{__init__,apps,models,admin}.py`, `operations/migrations/__init__.py`, `operations/migrations/0001_initial.py` (générée), `operations/migrations/0002_categories.py`
- Modify: `config/settings.py` (ajouter `"operations",` à `INSTALLED_APPS`), `tests/aides.py`
- Test: `tests/operations/__init__.py`, `tests/operations/test_modeles.py`

**Interfaces:**
- Consumes: `fiscal.Operation`, `fiscal.Nature` ; `biens.Bien`.
- Produces: `NatureOperation` (mêmes valeurs que `fiscal.Nature`) ; `Categorie` (`code`, `libelle`, `nature`, `ligne_2044` (`""` si aucune), `aide`, `source`, `active`, `ordre` ; propriétés `libelle_complet`, `classe_badge` ∈ `ri|ni|d|nd`) ; `Operation` (`bien`, `categorie`, `date_paiement`, `montant`, `libelle`, `justificatif`, `commentaire`, `releve` ; `vers_fiscal() -> fiscal.Operation`) ; `ReleveAgence` (`bien`, `periode`, `date_versement`, `loyer_brut`, `charges_recues`, `honoraires`, `commentaire`, propriété `net_verse`, relation `operations`) ; `valider_justificatif(fichier)`. Codes de catégories initiales : `loyer`, `depenses-locataire`, `subvention`, `indemnite-assurance`, `charges-locataire`, `depot-garantie`, `honoraires`, `frais-procedure`, `assurance-pno`, `travaux`, `charges-non-recuperees`, `indemnite-eviction`, `taxe-fonciere`, `provisions-copro`, `frais-emprunt`, `teom`, `travaux-non-deductibles`, `capital-emprunt`, `autre-non-deductible`. Aide de test `creer_operation(bien, code, montant, jour, libelle=None, **kw)`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/aides.py` :

```python
from operations.models import Categorie, Operation


def creer_operation(bien, code, montant, jour, libelle=None, **kw):
    return Operation.objects.create(
        bien=bien, categorie=Categorie.objects.get(code=code), date_paiement=jour, montant=montant,
        libelle=libelle or code, **kw,
    )
```

(placer l'import en tête du fichier.) `tests/operations/__init__.py` vide. `tests/operations/test_modeles.py` :

```python
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

import fiscal
from operations.models import Categorie, ReleveAgence, valider_justificatif
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def test_categories_initiales_presentes():
    travaux = Categorie.objects.get(code="travaux")
    assert (travaux.nature, travaux.ligne_2044) == ("CHARGE_DEDUCTIBLE", "224")
    assert Categorie.objects.get(code="teom").nature == "CHARGE_NON_DEDUCTIBLE"
    assert Categorie.objects.count() == 19


def test_toutes_les_categories_initiales_sont_coherentes():
    for categorie in Categorie.objects.all():
        categorie.full_clean()


def test_categorie_incoherente_refusee():
    with pytest.raises(ValidationError):
        Categorie(code="x", libelle="X", nature="CHARGE_DEDUCTIBLE", ligne_2044="211").full_clean()


def test_operation_vers_fiscal():
    o = creer_operation(creer_bien(), "travaux", 420_000, date(2025, 3, 12))
    assert o.vers_fiscal() == fiscal.Operation(
        id=o.pk, bien_id=o.bien_id, date_paiement=date(2025, 3, 12), montant=420_000,
        nature=fiscal.Nature.CHARGE_DEDUCTIBLE, ligne_2044="224", libelle="travaux",
    )


def test_operation_non_deductible_sans_ligne():
    o = creer_operation(creer_bien(), "teom", 16_800, date(2025, 10, 15))
    assert o.vers_fiscal().ligne_2044 is None


def test_justificatif_extension_refusee():
    with pytest.raises(ValidationError, match="Formats acceptés"):
        valider_justificatif(SimpleUploadedFile("virus.exe", b"MZ"))


def test_justificatif_trop_lourd_refuse():
    with pytest.raises(ValidationError, match="10 Mo"):
        valider_justificatif(SimpleUploadedFile("gros.pdf", b"0" * (10 * 1024 * 1024 + 1)))


def test_releve_net_verse():
    releve = ReleveAgence(loyer_brut=62_000, charges_recues=4_000, honoraires=4_340)
    assert releve.net_verse == 61_660
```

Run: `.venv/Scripts/python.exe -m pytest tests/operations -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'operations'`.

- [ ] **Step 2: Implémenter les modèles** — `operations/apps.py` (`OperationsConfig`, `verbose_name = "Opérations"`), fichiers `__init__.py` vides, puis `operations/models.py` :

```python
from datetime import date
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

import fiscal
from biens.models import Bien

EXTENSIONS_JUSTIFICATIF = {".pdf", ".jpg", ".jpeg", ".png"}
TAILLE_MAX_JUSTIFICATIF = 10 * 1024 * 1024


class NatureOperation(models.TextChoices):
    RECETTE_IMPOSABLE = "RECETTE_IMPOSABLE", "Recette imposable"
    RECETTE_NON_IMPOSABLE = "RECETTE_NON_IMPOSABLE", "Non imposable"
    CHARGE_DEDUCTIBLE = "CHARGE_DEDUCTIBLE", "Déductible"
    CHARGE_NON_DEDUCTIBLE = "CHARGE_NON_DEDUCTIBLE", "Non déductible"
    INTERETS = "INTERETS", "Intérêts · déductible"


CLASSES_BADGE = {
    NatureOperation.RECETTE_IMPOSABLE: "ri",
    NatureOperation.RECETTE_NON_IMPOSABLE: "ni",
    NatureOperation.CHARGE_DEDUCTIBLE: "d",
    NatureOperation.INTERETS: "d",
    NatureOperation.CHARGE_NON_DEDUCTIBLE: "nd",
}


def valider_justificatif(fichier):
    if Path(fichier.name).suffix.lower() not in EXTENSIONS_JUSTIFICATIF:
        raise ValidationError("Formats acceptés : PDF, JPEG ou PNG.")
    if fichier.size > TAILLE_MAX_JUSTIFICATIF:
        raise ValidationError("Le justificatif ne doit pas dépasser 10 Mo.")


def chemin_justificatif(instance, nom_fichier):
    annee = instance.date_paiement.year if instance.date_paiement else date.today().year
    return f"{annee}/{uuid4().hex}{Path(nom_fichier).suffix.lower()}"


class Categorie(models.Model):
    code = models.SlugField("code", unique=True)
    libelle = models.CharField("libellé", max_length=150)
    nature = models.CharField("nature", max_length=30, choices=NatureOperation.choices)
    ligne_2044 = models.CharField("ligne 2044", max_length=3, blank=True, default="")
    aide = models.TextField("aide", blank=True)
    source = models.CharField("source", max_length=150, blank=True)
    active = models.BooleanField("active", default=True)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        ordering = ["ordre", "libelle"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.libelle

    @property
    def libelle_complet(self):
        ligne = f", ligne {self.ligne_2044}" if self.ligne_2044 else ""
        return f"{self.libelle} ({self.get_nature_display().lower()}{ligne})"

    @property
    def classe_badge(self):
        return CLASSES_BADGE[self.nature]

    def clean(self):
        try:
            fiscal.Operation(
                id=0, bien_id=0, date_paiement=date(2000, 1, 1), montant=1, nature=self.nature,
                ligne_2044=self.ligne_2044 or None,
            )
        except ValueError as erreur:
            raise ValidationError({"ligne_2044": str(erreur)}) from None


class ReleveAgence(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="releves")
    periode = models.DateField("mois concerné")
    date_versement = models.DateField("date du versement")
    loyer_brut = models.BigIntegerField("loyer brut (centimes)")
    charges_recues = models.BigIntegerField("charges reçues du locataire (centimes)", default=0)
    honoraires = models.BigIntegerField("honoraires retenus (centimes)", default=0)
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        ordering = ["-periode"]
        verbose_name = "relevé d'agence"

    def __str__(self):
        return f"Relevé {self.periode:%m/%Y} — {self.bien}"

    @property
    def net_verse(self):
        return self.loyer_brut + self.charges_recues - self.honoraires


class Operation(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="operations")
    categorie = models.ForeignKey(Categorie, on_delete=models.PROTECT, related_name="operations")
    date_paiement = models.DateField("date de paiement")
    montant = models.BigIntegerField("montant (centimes)", validators=[MinValueValidator(1)])
    libelle = models.CharField("libellé", max_length=200)
    justificatif = models.FileField(
        "justificatif", upload_to=chemin_justificatif, blank=True, validators=[valider_justificatif]
    )
    commentaire = models.TextField("commentaire", blank=True)
    releve = models.ForeignKey(
        ReleveAgence, on_delete=models.CASCADE, null=True, blank=True, related_name="operations"
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_paiement", "-id"]
        verbose_name = "opération"

    def __str__(self):
        return f"{self.date_paiement:%d/%m/%Y} — {self.libelle}"

    def vers_fiscal(self) -> fiscal.Operation:
        return fiscal.Operation(
            id=self.pk, bien_id=self.bien_id, date_paiement=self.date_paiement, montant=self.montant,
            nature=self.categorie.nature, ligne_2044=self.categorie.ligne_2044 or None, libelle=self.libelle,
        )
```

`operations/admin.py` :

```python
from django.contrib import admin

from .models import Categorie


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ["libelle", "nature", "ligne_2044", "active", "ordre"]
    list_filter = ["nature", "active"]
```

Ajouter `"operations",` à la fin d'`INSTALLED_APPS`.

Run: `DJANGO_DEBUG=1 .venv/Scripts/python.exe manage.py makemigrations operations`
Expected: `Migrations for 'operations': operations/migrations/0001_initial.py`

- [ ] **Step 3: Migration des catégories initiales** — `operations/migrations/0002_categories.py`

```python
from django.db import migrations

NOTICE = "Notice 2044"
CATEGORIES = [
    ("loyer", "Loyer encaissé", "RECETTE_IMPOSABLE", "211",
     "Loyer hors charges réellement encaissé, avant honoraires d'agence.", NOTICE),
    ("depenses-locataire", "Dépense du propriétaire payée par le locataire", "RECETTE_IMPOSABLE", "212",
     "Dépense incombant normalement au propriétaire et mise à la charge du locataire.", NOTICE),
    ("subvention", "Subvention ANAH ou indemnité pour travaux", "RECETTE_IMPOSABLE", "213", "", NOTICE),
    ("indemnite-assurance", "Indemnité d'assurance (perte de loyers)", "RECETTE_IMPOSABLE", "214", "", NOTICE),
    ("charges-locataire", "Provision ou remboursement de charges par le locataire", "RECETTE_NON_IMPOSABLE", "",
     "Non imposable : les charges récupérables refacturées au locataire ne sont pas des loyers.", NOTICE),
    ("depot-garantie", "Dépôt de garantie reçu", "RECETTE_NON_IMPOSABLE", "",
     "Non imposable tant qu'il n'est pas conservé pour couvrir des loyers impayés.", NOTICE),
    ("honoraires", "Honoraires d'agence et frais de gestion", "CHARGE_DEDUCTIBLE", "221",
     "Honoraires de gestion, de location et de rédaction de bail à la charge du propriétaire.",
     "BOFiP BOI-RFPI-BASE-20-10"),
    ("frais-procedure", "Frais de procédure, d'avocat ou d'huissier", "CHARGE_DEDUCTIBLE", "221", "",
     "BOFiP BOI-RFPI-BASE-20-10"),
    ("assurance-pno", "Assurance propriétaire non occupant ou loyers impayés", "CHARGE_DEDUCTIBLE", "223", "",
     NOTICE),
    ("travaux", "Travaux de réparation, d'entretien et d'amélioration", "CHARGE_DEDUCTIBLE", "224",
     "Déductibles sauf travaux de construction, de reconstruction ou d'agrandissement.",
     "BOFiP BOI-RFPI-BASE-20-30"),
    ("charges-non-recuperees", "Charges récupérables non récupérées", "CHARGE_DEDUCTIBLE", "225",
     "Charges récupérables restées à votre charge au départ du locataire.", NOTICE),
    ("indemnite-eviction", "Indemnité d'éviction ou frais de relogement", "CHARGE_DEDUCTIBLE", "226", "", NOTICE),
    ("taxe-fonciere", "Taxe foncière (hors ordures ménagères)", "CHARGE_DEDUCTIBLE", "227",
     "Saisissez la taxe d'enlèvement des ordures ménagères à part : elle n'est pas déductible.", NOTICE),
    ("provisions-copro", "Provisions de charges de copropriété (appels de fonds)", "CHARGE_DEDUCTIBLE", "229",
     "La part non déductible sera régularisée l'année suivante (décompte du syndic).", NOTICE),
    ("frais-emprunt", "Frais d'emprunt hors échéancier (dossier, garantie)", "INTERETS", "250",
     "Les intérêts et l'assurance des échéances viennent du tableau d'amortissement.",
     "BOFiP BOI-RFPI-BASE-20-80"),
    ("teom", "Taxe d'enlèvement des ordures ménagères", "CHARGE_NON_DEDUCTIBLE", "",
     "Récupérable sur le locataire, non déductible.", NOTICE),
    ("travaux-non-deductibles", "Travaux de construction, reconstruction ou agrandissement",
     "CHARGE_NON_DEDUCTIBLE", "", "", "BOFiP BOI-RFPI-BASE-20-30"),
    ("capital-emprunt", "Capital d'emprunt remboursé", "CHARGE_NON_DEDUCTIBLE", "",
     "Seuls les intérêts sont déductibles.", "BOFiP BOI-RFPI-BASE-20-80"),
    ("autre-non-deductible", "Autre dépense non déductible", "CHARGE_NON_DEDUCTIBLE", "", "", NOTICE),
]


def creer(apps, schema_editor):
    Categorie = apps.get_model("operations", "Categorie")
    Categorie.objects.bulk_create(
        Categorie(code=code, libelle=libelle, nature=nature, ligne_2044=ligne, aide=aide, source=source, ordre=i)
        for i, (code, libelle, nature, ligne, aide, source) in enumerate(CATEGORIES)
    )


def supprimer(apps, schema_editor):
    apps.get_model("operations", "Categorie").objects.filter(code__in=[c[0] for c in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]
    operations = [migrations.RunPython(creer, supprimer)]
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `103 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(operations): catégories, opérations et relevés d'agence"
```

---

### Task 7: Écrans des opérations et justificatifs protégés

**Files:**
- Create: `operations/forms.py`, `operations/views.py`, `operations/urls.py`, `templates/operations/liste.html`
- Modify: `config/urls.py` (ajouter `path("operations/", include("operations.urls")),`)
- Test: `tests/operations/test_vues.py`

**Interfaces:**
- Consumes: Task 6 (modèles), Task 3 (`MontantField`, `euros`), Task 5 (`commun/formulaire.html`).
- Produces: URLs `operations:liste` (`/operations/`, filtres GET `annee`, `bien`, `nature` ∈ `recettes|deductibles|non-deductibles`), `operations:creer` (`/operations/nouvelle/`, GET `bien` présélectionne), `operations:modifier`, `operations:supprimer` (POST), `operations:justificatif`. Forme `OperationForm`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/operations/test_vues.py`

```python
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from operations.models import Categorie, Operation
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def donnees(bien, **kw):
    d = {
        "bien": bien.pk, "date_paiement": "2025-07-01", "categorie": Categorie.objects.get(code="travaux").pk,
        "libelle": "Remplacement du chauffe-eau", "montant": "1 180", "commentaire": "",
    }
    d.update(kw)
    return d


def test_creation_avec_justificatif(client_verifie):
    b = creer_bien()
    fichier = SimpleUploadedFile("facture.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    r = client_verifie.post(reverse("operations:creer"), donnees(b, justificatif=fichier))
    assert r.status_code == 302
    op = Operation.objects.get()
    assert op.montant == 118_000
    assert op.justificatif.name.endswith(".pdf")


def test_justificatif_au_mauvais_format_refuse(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("operations:creer"), donnees(b, justificatif=SimpleUploadedFile("x.exe", b"MZ")))
    assert r.status_code == 200
    assert "Formats acceptés" in r.content.decode()
    assert not Operation.objects.exists()


def test_filtre_par_nature(client_verifie):
    b = creer_bien()
    creer_operation(b, "loyer", 62_000, date(2025, 9, 5), "Loyer septembre")
    creer_operation(b, "teom", 16_800, date(2025, 10, 15), "Ordures ménagères")
    contenu = client_verifie.get(reverse("operations:liste") + "?annee=2025&nature=non-deductibles").content.decode()
    assert "Ordures ménagères" in contenu
    assert "Loyer septembre" not in contenu


def test_annee_par_defaut_la_plus_recente(client_verifie):
    b = creer_bien()
    creer_operation(b, "loyer", 62_000, date(2024, 9, 5), "Loyer 2024")
    creer_operation(b, "loyer", 62_000, date(2025, 9, 5), "Loyer 2025")
    contenu = client_verifie.get(reverse("operations:liste")).content.decode()
    assert "Loyer 2025" in contenu
    assert "Loyer 2024" not in contenu


def test_justificatif_protege(client_verifie):
    b = creer_bien()
    op = creer_operation(
        b, "travaux", 1000, date(2025, 1, 2), justificatif=SimpleUploadedFile("f.pdf", b"%PDF contenu")
    )
    url = reverse("operations:justificatif", args=[op.pk])
    assert Client().get(url).status_code == 302
    r = client_verifie.get(url)
    assert r.status_code == 200
    assert b"".join(r.streaming_content) == b"%PDF contenu"


def test_suppression_uniquement_en_post(client_verifie):
    op = creer_operation(creer_bien(), "loyer", 62_000, date(2025, 1, 5))
    url = reverse("operations:supprimer", args=[op.pk])
    assert client_verifie.get(url).status_code == 405
    assert client_verifie.post(url).status_code == 302
    assert not Operation.objects.exists()
```

Run: `.venv/Scripts/python.exe -m pytest tests/operations/test_vues.py -q`
Expected: FAIL (`NoReverseMatch: 'operations' is not a registered namespace`).

- [ ] **Step 2: Formulaire** — `operations/forms.py`

```python
from django import forms

from commun.forms import MontantField

from .models import Categorie, Operation


class CategorieChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.libelle_complet


class OperationForm(forms.ModelForm):
    categorie = CategorieChoiceField(queryset=Categorie.objects.filter(active=True), label="Catégorie")
    montant = MontantField(label="Montant (€)")

    class Meta:
        model = Operation
        fields = ["bien", "date_paiement", "categorie", "libelle", "montant", "justificatif", "commentaire"]
        widgets = {
            "date_paiement": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "commentaire": forms.Textarea(attrs={"rows": 2}),
        }
```

- [ ] **Step 3: Vues et routes** — `operations/views.py`

```python
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from biens.models import Bien

from .forms import OperationForm
from .models import NatureOperation, Operation

FILTRES_NATURE = {
    "recettes": [NatureOperation.RECETTE_IMPOSABLE, NatureOperation.RECETTE_NON_IMPOSABLE],
    "deductibles": [NatureOperation.CHARGE_DEDUCTIBLE, NatureOperation.INTERETS],
    "non-deductibles": [NatureOperation.CHARGE_NON_DEDUCTIBLE],
}
PUCES = (("", "Toutes"), ("recettes", "Recettes"), ("deductibles", "Déductibles"), ("non-deductibles", "Non déductibles"))


def _requete(params):
    return "?" + urlencode({k: v for k, v in params.items() if v not in ("", None)})


def liste(request):
    annees = sorted({d.year for d in Operation.objects.dates("date_paiement", "year")}, reverse=True)
    try:
        annee = int(request.GET.get("annee") or (annees[0] if annees else date.today().year))
    except ValueError:
        annee = date.today().year
    if annee not in annees:
        annees = sorted({*annees, annee}, reverse=True)
    requete = Operation.objects.filter(date_paiement__year=annee).select_related("bien", "categorie")
    bien_id = request.GET.get("bien", "")
    bien_id = int(bien_id) if bien_id.isdigit() else None
    if bien_id:
        requete = requete.filter(bien_id=bien_id)
    nature = request.GET.get("nature", "")
    if nature in FILTRES_NATURE:
        requete = requete.filter(categorie__nature__in=FILTRES_NATURE[nature])
    else:
        nature = ""
    operations = list(requete)
    totaux = {
        "recettes": sum(o.montant for o in operations if o.categorie.nature == NatureOperation.RECETTE_IMPOSABLE),
        "deductibles": sum(o.montant for o in operations if o.categorie.nature in FILTRES_NATURE["deductibles"]),
        "non_deductibles": sum(
            o.montant for o in operations if o.categorie.nature == NatureOperation.CHARGE_NON_DEDUCTIBLE
        ),
    }
    base = {"annee": annee, "bien": bien_id}
    puces = [
        {"libelle": libelle, "url": _requete({**base, "nature": code}), "actif": code == nature}
        for code, libelle in PUCES
    ]
    return render(request, "operations/liste.html", {
        "operations": operations, "annee": annee, "annees": annees, "biens": Bien.objects.all(),
        "bien_id": bien_id, "nature": nature, "puces": puces, "totaux": totaux,
    })


def creer(request):
    initial = {"date_paiement": date.today(), "bien": request.GET.get("bien")}
    return _formulaire(request, Operation(), initial)


def modifier(request, pk):
    return _formulaire(request, get_object_or_404(Operation, pk=pk), None)


def _formulaire(request, operation, initial):
    form = OperationForm(request.POST or None, request.FILES or None, instance=operation, initial=initial)
    if request.method == "POST" and form.is_valid():
        operation = form.save()
        messages.success(request, f"Opération « {operation.libelle} » enregistrée.")
        return redirect(f"{reverse('operations:liste')}?annee={operation.date_paiement.year}")
    contexte = {
        "form": form,
        "titre": "Modifier l'opération" if operation.pk else "Nouvelle opération",
        "retour": reverse("operations:liste"),
    }
    if operation.pk:
        contexte["suppression"] = reverse("operations:supprimer", args=[operation.pk])
    return render(request, "commun/formulaire.html", contexte)


@require_POST
def supprimer(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    annee = operation.date_paiement.year
    operation.delete()
    messages.success(request, "Opération supprimée.")
    return redirect(f"{reverse('operations:liste')}?annee={annee}")


def justificatif(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    if not operation.justificatif:
        raise Http404("Aucun justificatif.")
    return FileResponse(operation.justificatif.open("rb"), filename=Path(operation.justificatif.name).name)
```

`operations/urls.py` :

```python
from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouvelle/", views.creer, name="creer"),
    path("<int:pk>/", views.modifier, name="modifier"),
    path("<int:pk>/supprimer/", views.supprimer, name="supprimer"),
    path("<int:pk>/justificatif/", views.justificatif, name="justificatif"),
]
```

Dans `config/urls.py`, ajouter `path("operations/", include("operations.urls")),` après `biens/`.

- [ ] **Step 4: Gabarit** — `templates/operations/liste.html`

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Opérations{% endblock %}
{% block contenu %}
<header class="entete">
  <div><h1>Opérations</h1><p class="sous-titre">{{ annee }} · classées par date de paiement</p></div>
  <div class="actions">
    <a class="bouton principal" href="{% url 'operations:creer' %}">+ Nouvelle opération</a>
  </div>
</header>
<form method="get" class="filtres">
  <div class="champ">
    <label for="f-annee">Année</label>
    <select id="f-annee" name="annee">{% for a in annees %}<option value="{{ a }}"{% if a == annee %} selected{% endif %}>{{ a }}</option>{% endfor %}</select>
  </div>
  <div class="champ">
    <label for="f-bien">Bien</label>
    <select id="f-bien" name="bien"><option value="">Tous les biens</option>{% for b in biens %}<option value="{{ b.pk }}"{% if b.pk == bien_id %} selected{% endif %}>{{ b.nom }}</option>{% endfor %}</select>
  </div>
  <input type="hidden" name="nature" value="{{ nature }}">
  <button class="bouton" type="submit">Filtrer</button>
</form>
<nav class="puces" aria-label="Filtrer par nature">
  {% for p in puces %}<a href="{{ p.url }}"{% if p.actif %} class="actif" aria-current="true"{% endif %}>{{ p.libelle }}</a>{% endfor %}
</nav>
<div class="grille">
  <div class="carte"><span class="sous-titre">Recettes imposables</span><strong class="chiffre">{{ totaux.recettes|euros }}</strong></div>
  <div class="carte"><span class="sous-titre">Charges déductibles saisies</span><strong class="chiffre">{{ totaux.deductibles|euros }}</strong><span class="helptext">Hors intérêts des échéances de prêt</span></div>
  <div class="carte"><span class="sous-titre">Non déductible</span><strong class="chiffre">{{ totaux.non_deductibles|euros }}</strong></div>
</div>
<div class="carte tableau">
<table>
  <thead><tr><th>Date</th><th>Bien</th><th>Libellé</th><th>Ligne</th><th>Nature</th><th class="montant">Montant</th><th><span class="sr">Actions</span></th></tr></thead>
  <tbody>
  {% for op in operations %}
    <tr>
      <td>{{ op.date_paiement|date:"d/m/Y" }}</td>
      <td>{{ op.bien.nom }}</td>
      <td>{{ op.libelle }}{% if op.justificatif %} · <a href="{% url 'operations:justificatif' op.pk %}">justificatif</a>{% endif %}</td>
      <td>{{ op.categorie.ligne_2044|default:"—" }}</td>
      <td><span class="badge {{ op.categorie.classe_badge }}">{{ op.categorie.get_nature_display }}</span></td>
      <td class="montant">{{ op.montant|euros }}</td>
      <td><a href="{% url 'operations:modifier' op.pk %}">Modifier</a></td>
    </tr>
  {% empty %}
    <tr><td colspan="7">Aucune opération pour ces critères.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `109 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(operations): liste filtrable, saisie et justificatifs protégés"
```

---

### Task 8: Saisie d'un relevé d'agence

**Files:**
- Create: `operations/services.py`
- Modify: `operations/forms.py`, `operations/views.py`, `operations/urls.py`, `templates/operations/liste.html`
- Test: `tests/operations/test_releves.py`

**Interfaces:**
- Consumes: `ReleveAgence`, `Operation`, `Categorie` (codes `loyer`, `charges-locataire`, `honoraires`).
- Produces: `enregistrer_releve(releve: ReleveAgence) -> list[Operation]` (enregistre le relevé et **remplace** ses opérations : loyer 211, charges non imposables, honoraires 221 ; montants nuls ignorés) ; `ReleveForm` ; URLs `operations:creer_releve` (`/operations/releves/nouveau/`), `operations:modifier_releve`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/operations/test_releves.py`

```python
from datetime import date

import pytest
from django.urls import reverse

from operations.models import Operation, ReleveAgence
from operations.services import enregistrer_releve
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def releve(bien, **kw):
    d = dict(bien=bien, periode=date(2025, 9, 1), date_versement=date(2025, 9, 5), loyer_brut=62_000,
             charges_recues=4_000, honoraires=4_340)
    d.update(kw)
    return ReleveAgence(**d)


def test_releve_genere_trois_operations():
    ops = enregistrer_releve(releve(creer_bien()))
    assert sorted((o.categorie.code, o.montant) for o in ops) == [
        ("charges-locataire", 4_000), ("honoraires", 4_340), ("loyer", 62_000)
    ]
    assert all(o.date_paiement == date(2025, 9, 5) for o in ops)


def test_releve_sans_honoraires_ni_charges():
    ops = enregistrer_releve(releve(creer_bien(), charges_recues=0, honoraires=0))
    assert [o.categorie.code for o in ops] == ["loyer"]


def test_modifier_un_releve_ne_cree_pas_de_doublon():
    r = releve(creer_bien())
    enregistrer_releve(r)
    r.loyer_brut = 63_000
    enregistrer_releve(r)
    assert Operation.objects.count() == 3
    assert Operation.objects.get(categorie__code="loyer").montant == 63_000


def test_saisie_d_un_releve_par_l_ecran(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("operations:creer_releve"), {
        "bien": b.pk, "periode": "2025-09", "date_versement": "2025-09-05", "loyer_brut": "620",
        "charges_recues": "40", "honoraires": "43,40", "commentaire": "",
    })
    assert r.status_code == 302
    assert Operation.objects.filter(releve__isnull=False).count() == 3


def test_honoraires_superieurs_aux_sommes_recues_refuses(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("operations:creer_releve"), {
        "bien": b.pk, "periode": "2025-09", "date_versement": "2025-09-05", "loyer_brut": "100",
        "charges_recues": "", "honoraires": "200", "commentaire": "",
    })
    assert r.status_code == 200
    assert not ReleveAgence.objects.exists()
```

Run: `.venv/Scripts/python.exe -m pytest tests/operations/test_releves.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'operations.services'`.

- [ ] **Step 2: Service** — `operations/services.py`

```python
from django.db import transaction

from .models import Categorie, Operation, ReleveAgence


@transaction.atomic
def enregistrer_releve(releve: ReleveAgence) -> list[Operation]:
    """Enregistre le relevé et remplace ses opérations (loyer, charges, honoraires)."""
    releve.save()
    releve.operations.all().delete()
    mois = f"{releve.periode:%m/%Y}"
    lignes = [
        ("loyer", releve.loyer_brut, f"Relevé agence {mois} — loyer"),
        ("charges-locataire", releve.charges_recues, f"Relevé agence {mois} — charges"),
        ("honoraires", releve.honoraires, f"Relevé agence {mois} — honoraires"),
    ]
    return [
        Operation.objects.create(
            bien=releve.bien, categorie=Categorie.objects.get(code=code), date_paiement=releve.date_versement,
            montant=montant, libelle=libelle, releve=releve,
        )
        for code, montant, libelle in lignes
        if montant > 0
    ]
```

- [ ] **Step 3: Formulaire, vues, routes**

Ajouter à `operations/forms.py` (et `ReleveAgence` à l'import des modèles) :

```python
class ReleveForm(forms.ModelForm):
    periode = forms.DateField(
        label="Mois concerné", input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )
    loyer_brut = MontantField(label="Loyer brut (€)")
    charges_recues = MontantField(label="Charges reçues du locataire (€)", required=False, minimum=0, valeur_si_vide=0)
    honoraires = MontantField(label="Honoraires retenus par l'agence (€)", required=False, minimum=0, valeur_si_vide=0)

    class Meta:
        model = ReleveAgence
        fields = ["bien", "periode", "date_versement", "loyer_brut", "charges_recues", "honoraires", "commentaire"]
        widgets = {
            "date_versement": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "commentaire": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        donnees = super().clean()
        recu = (donnees.get("loyer_brut") or 0) + (donnees.get("charges_recues") or 0)
        if (donnees.get("honoraires") or 0) > recu:
            raise forms.ValidationError("Les honoraires dépassent les sommes reçues du locataire.")
        return donnees
```

Ajouter à `operations/views.py` (imports : `ReleveForm` depuis `.forms`, `ReleveAgence` depuis `.models`, `enregistrer_releve` depuis `.services`, `format_euros` depuis `commun.montants`) :

```python
def creer_releve(request):
    return _formulaire_releve(request, ReleveAgence())


def modifier_releve(request, pk):
    return _formulaire_releve(request, get_object_or_404(ReleveAgence, pk=pk))


def _formulaire_releve(request, releve):
    form = ReleveForm(request.POST or None, instance=releve)
    if request.method == "POST" and form.is_valid():
        releve = form.save(commit=False)
        operations = enregistrer_releve(releve)
        messages.success(
            request,
            f"{len(operations)} opérations enregistrées (net versé : {format_euros(releve.net_verse)}).",
        )
        return redirect(f"{reverse('operations:liste')}?annee={releve.date_versement.year}")
    return render(request, "commun/formulaire.html", {
        "form": form,
        "titre": "Relevé d'agence",
        "intro": "Le relevé est découpé en loyer brut (ligne 211), charges (non imposables) et honoraires (ligne 221).",
        "retour": reverse("operations:liste"),
    })
```

Dans `operations/urls.py`, ajouter :

```python
    path("releves/nouveau/", views.creer_releve, name="creer_releve"),
    path("releves/<int:pk>/", views.modifier_releve, name="modifier_releve"),
```

Dans `templates/operations/liste.html`, dans le bloc `<div class="actions">`, ajouter avant le lien « Nouvelle opération » :

```html
    <a class="bouton" href="{% url 'operations:creer_releve' %}">Saisir un relevé d'agence</a>
```

et remplacer la cellule de la colonne Actions par :

```html
      <td>{% if op.releve_id %}<a href="{% url 'operations:modifier_releve' op.releve_id %}">Relevé</a>{% else %}<a href="{% url 'operations:modifier' op.pk %}">Modifier</a>{% endif %}</td>
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `114 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(operations): saisie d'un relevé d'agence"
```

---

### Task 9: Crédit — prêts, échéances et import CSV

**Files:**
- Create: `credit/{__init__,apps,models,import_csv,forms,views,urls}.py`, `credit/migrations/__init__.py`, `credit/migrations/0001_initial.py` (générée), `templates/credit/{liste,detail,import_fichier,import_colonnes}.html`
- Modify: `config/settings.py` (`"credit",`), `config/urls.py` (`path("credit/", include("credit.urls")),`)
- Test: `tests/credit/__init__.py`, `tests/credit/test_import_csv.py`, `tests/credit/test_vues.py`

**Interfaces:**
- Consumes: `commun.montants.parse_euros`, `MontantField`, `biens.Bien`.
- Produces: `Pret` (`bien`, `banque`, `libelle`, `capital_emprunte`, `date_debut` ; relation `echeances`), `Echeance` (`pret`, `date`, `capital`, `interets`, `assurance`, `frais` ; propriété `deductible` ; unique par `(pret, date)`) ; `credit.import_csv` : `ErreurImport(ValueError)`, `Colonnes(date, capital, interets, assurance="")`, `EcheanceLue(date, capital, interets, assurance)`, `decoder(contenu: bytes) -> str`, `lire_entetes(texte) -> list[str]`, `lire_echeancier(texte, colonnes) -> list[EcheanceLue]` ; URLs `credit:liste`, `credit:creer`, `credit:detail`, `credit:modifier`, `credit:importer`.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/credit/__init__.py` vide. `tests/credit/test_import_csv.py` :

```python
from datetime import date

import pytest

from credit.import_csv import Colonnes, EcheanceLue, ErreurImport, decoder, lire_echeancier, lire_entetes

CSV_FR = "Date;Capital amorti;Intérêts;Assurance\n05/01/2025;612,45;173,20;18,00\n05/02/2025;613,10;172,55;18,00\n\n"
COLONNES_FR = Colonnes("Date", "Capital amorti", "Intérêts", "Assurance")


def test_format_francais():
    lues = lire_echeancier(CSV_FR, COLONNES_FR)
    assert len(lues) == 2
    assert lues[0] == EcheanceLue(date(2025, 1, 5), 61_245, 17_320, 1_800)


def test_virgule_et_point_decimal_sans_assurance():
    lues = lire_echeancier("date,capital,interets\n2025-01-05,612.45,173.20\n", Colonnes("date", "capital", "interets"))
    assert lues == [EcheanceLue(date(2025, 1, 5), 61_245, 17_320, 0)]


def test_colonne_introuvable():
    with pytest.raises(ErreurImport, match="Colonnes introuvables"):
        lire_echeancier(CSV_FR, Colonnes("Date", "Capital", "Intérêts"))


def test_ligne_invalide_indique_son_numero():
    with pytest.raises(ErreurImport, match="Ligne 3"):
        lire_echeancier("Date;Capital;Intérêts\n05/01/2025;1;1\nxx;1;1\n", Colonnes("Date", "Capital", "Intérêts"))


def test_decodage_cp1252_et_bom():
    assert decoder("Intérêts".encode("cp1252")) == "Intérêts"
    assert decoder("\ufeffDate".encode("utf-8")) == "Date"


def test_entetes():
    assert lire_entetes(CSV_FR) == ["Date", "Capital amorti", "Intérêts", "Assurance"]


def test_fichier_sans_echeance():
    with pytest.raises(ErreurImport, match="Aucune échéance"):
        lire_echeancier("Date;Capital;Intérêts\n", Colonnes("Date", "Capital", "Intérêts"))
```

`tests/credit/test_vues.py` :

```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from credit.models import Echeance, Pret
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db
CSV_FR = "Date;Capital amorti;Intérêts;Assurance\n05/01/2025;612,45;173,20;18,00\n05/02/2025;613,10;172,55;18,00\n"
MAPPING = {"date": "Date", "capital": "Capital amorti", "interets": "Intérêts", "assurance": "Assurance"}


def creer_pret():
    return Pret.objects.create(bien=creer_bien(), banque="Banque", capital_emprunte=15_000_000, date_debut="2015-01-05")


def test_creation_d_un_pret(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("credit:creer"), {
        "bien": b.pk, "banque": "Banque", "libelle": "", "capital_emprunte": "150 000", "date_debut": "2015-01-05",
    })
    assert r.status_code == 302
    assert Pret.objects.get().capital_emprunte == 15_000_000


def test_import_en_trois_etapes_sans_doublon(client_verifie):
    pret = creer_pret()
    url = reverse("credit:importer", args=[pret.pk])
    fichier = SimpleUploadedFile("echeancier.csv", CSV_FR.encode("cp1252"))
    assert client_verifie.post(url, {"fichier": fichier}).status_code == 302
    assert "Colonne de la date" in client_verifie.get(url).content.decode()
    apercu = client_verifie.post(url, {**MAPPING, "apercu": "1"})
    assert "2 échéances" in apercu.content.decode()
    assert client_verifie.post(url, {**MAPPING, "importer": "1"}).status_code == 302
    assert Echeance.objects.filter(pret=pret).count() == 2
    client_verifie.post(url, {"fichier": SimpleUploadedFile("e.csv", CSV_FR.encode("utf-8"))})
    client_verifie.post(url, {**MAPPING, "importer": "1"})
    assert Echeance.objects.filter(pret=pret).count() == 2


def test_detail_affiche_les_totaux_annuels(client_verifie):
    pret = creer_pret()
    Echeance.objects.create(pret=pret, date="2025-01-05", capital=61_245, interets=17_320, assurance=1_800)
    Echeance.objects.create(pret=pret, date="2025-02-05", capital=61_310, interets=17_255, assurance=1_800)
    contenu = client_verifie.get(reverse("credit:detail", args=[pret.pk])).content.decode()
    assert "381,75 €" in contenu
```

(381,75 € = intérêts 345,75 € + assurance 36,00 €, colonne « Déductible (ligne 250) ».)

Run: `.venv/Scripts/python.exe -m pytest tests/credit -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'credit'`.

- [ ] **Step 2: Modèles et import CSV**

`credit/apps.py` (`CreditConfig`, `verbose_name = "Crédit"`), fichiers `__init__.py` vides. `credit/models.py` :

```python
from django.db import models
from django.urls import reverse

from biens.models import Bien


class Pret(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="prets")
    banque = models.CharField("banque", max_length=100)
    libelle = models.CharField("libellé", max_length=100, blank=True)
    capital_emprunte = models.BigIntegerField("capital emprunté (centimes)")
    date_debut = models.DateField("date de début")

    class Meta:
        ordering = ["bien__nom", "date_debut"]
        verbose_name = "prêt"

    def __str__(self):
        return f"{self.banque} — {self.bien}"

    def get_absolute_url(self):
        return reverse("credit:detail", args=[self.pk])


class Echeance(models.Model):
    pret = models.ForeignKey(Pret, on_delete=models.CASCADE, related_name="echeances")
    date = models.DateField("date")
    capital = models.BigIntegerField("capital (centimes)", default=0)
    interets = models.BigIntegerField("intérêts (centimes)", default=0)
    assurance = models.BigIntegerField("assurance emprunteur (centimes)", default=0)
    frais = models.BigIntegerField("frais (centimes)", default=0)

    class Meta:
        ordering = ["date"]
        verbose_name = "échéance"
        constraints = [models.UniqueConstraint(fields=["pret", "date"], name="echeance_unique_par_date")]

    @property
    def deductible(self):
        return self.interets + self.assurance + self.frais
```

`credit/import_csv.py` :

```python
"""Lecture d'un tableau d'amortissement exporté par la banque (CSV)."""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

from commun.montants import parse_euros

FORMATS_DATE = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y")


class ErreurImport(ValueError):
    pass


@dataclass(frozen=True)
class Colonnes:
    date: str
    capital: str
    interets: str
    assurance: str = ""


@dataclass(frozen=True)
class EcheanceLue:
    date: date
    capital: int
    interets: int
    assurance: int


def decoder(contenu: bytes) -> str:
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenu.decode("cp1252")


def _separateur(texte: str) -> str:
    entete = next((ligne for ligne in texte.splitlines() if ligne.strip()), "")
    return max((";", "\t", ","), key=entete.count)


def lire_entetes(texte: str) -> list[str]:
    lecteur = csv.reader(io.StringIO(texte), delimiter=_separateur(texte))
    for ligne in lecteur:
        if any(cellule.strip() for cellule in ligne):
            return [cellule.strip() for cellule in ligne]
    raise ErreurImport("Le fichier est vide.")


def _date(valeur: str) -> date:
    for format_date in FORMATS_DATE:
        try:
            return datetime.strptime(valeur.strip(), format_date).date()
        except ValueError:
            continue
    raise ValueError(f"date invalide {valeur!r}")


def _montant(valeur: str | None) -> int:
    valeur = (valeur or "").strip()
    return 0 if not valeur else abs(parse_euros(valeur))


def lire_echeancier(texte: str, colonnes: Colonnes) -> list[EcheanceLue]:
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=_separateur(texte))
    entetes = [e.strip() for e in (lecteur.fieldnames or [])]
    lecteur.fieldnames = entetes
    voulues = [c for c in (colonnes.date, colonnes.capital, colonnes.interets, colonnes.assurance) if c]
    manquantes = [c for c in voulues if c not in entetes]
    if manquantes:
        raise ErreurImport(f"Colonnes introuvables : {', '.join(manquantes)}")
    lues = []
    for ligne in lecteur:
        if all(not (v or "").strip() for k, v in ligne.items() if k is not None and isinstance(v, str | None)):
            continue
        try:
            lues.append(EcheanceLue(
                _date(ligne[colonnes.date] or ""),
                _montant(ligne[colonnes.capital]),
                _montant(ligne[colonnes.interets]),
                _montant(ligne[colonnes.assurance]) if colonnes.assurance else 0,
            ))
        except ValueError as erreur:
            raise ErreurImport(f"Ligne {lecteur.line_num} : {erreur}") from None
    if not lues:
        raise ErreurImport("Aucune échéance trouvée dans le fichier.")
    return lues
```

Ajouter `"credit",` à `INSTALLED_APPS`.

Run: `DJANGO_DEBUG=1 .venv/Scripts/python.exe manage.py makemigrations credit`
Expected: `Migrations for 'credit': credit/migrations/0001_initial.py`

- [ ] **Step 3: Formulaires, vues, routes**

`credit/forms.py` :

```python
from django import forms

from commun.forms import MontantField

from .import_csv import Colonnes
from .models import Pret


class PretForm(forms.ModelForm):
    capital_emprunte = MontantField(label="Capital emprunté (€)")

    class Meta:
        model = Pret
        fields = ["bien", "banque", "libelle", "capital_emprunte", "date_debut"]
        widgets = {"date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


def _deviner(entetes, *mots):
    for entete in entetes:
        if any(mot in entete.lower() for mot in mots):
            return entete
    return None


class ColonnesForm(forms.Form):
    def __init__(self, entetes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choix = [(e, e) for e in entetes]
        self.fields["date"] = forms.ChoiceField(
            label="Colonne de la date", choices=choix, initial=_deviner(entetes, "date", "échéance")
        )
        self.fields["capital"] = forms.ChoiceField(
            label="Colonne du capital remboursé", choices=choix, initial=_deviner(entetes, "capital", "amorti")
        )
        self.fields["interets"] = forms.ChoiceField(
            label="Colonne des intérêts", choices=choix, initial=_deviner(entetes, "intér", "interet")
        )
        self.fields["assurance"] = forms.ChoiceField(
            label="Colonne de l'assurance emprunteur", choices=[("", "— aucune —"), *choix], required=False,
            initial=_deviner(entetes, "assur"),
        )

    def colonnes(self) -> Colonnes:
        return Colonnes(**self.cleaned_data)
```

`credit/views.py` :

```python
from collections import defaultdict

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ColonnesForm, PretForm
from .import_csv import ErreurImport, decoder, lire_echeancier, lire_entetes
from .models import Echeance, Pret

TAILLE_MAX_CSV = 1_000_000


def liste(request):
    return render(request, "credit/liste.html", {"prets": Pret.objects.select_related("bien")})


def creer(request):
    return _formulaire(request, Pret())


def modifier(request, pk):
    return _formulaire(request, get_object_or_404(Pret, pk=pk))


def _formulaire(request, pret):
    form = PretForm(request.POST or None, instance=pret)
    if request.method == "POST" and form.is_valid():
        pret = form.save()
        messages.success(request, "Prêt enregistré.")
        return redirect(pret)
    titre = "Modifier le prêt" if pret.pk else "Nouveau prêt"
    return render(request, "commun/formulaire.html", {"form": form, "titre": titre, "retour": reverse("credit:liste")})


def detail(request, pk):
    pret = get_object_or_404(Pret.objects.select_related("bien"), pk=pk)
    echeances = list(pret.echeances.all())
    par_annee = defaultdict(lambda: {"capital": 0, "interets": 0, "assurance": 0, "frais": 0, "deductible": 0})
    for e in echeances:
        total = par_annee[e.date.year]
        total["capital"] += e.capital
        total["interets"] += e.interets
        total["assurance"] += e.assurance
        total["frais"] += e.frais
        total["deductible"] += e.deductible
    annees = [{"annee": a, **t} for a, t in sorted(par_annee.items(), reverse=True)]
    return render(request, "credit/detail.html", {"pret": pret, "echeances": echeances, "annees": annees})


def importer(request, pk):
    pret = get_object_or_404(Pret, pk=pk)
    cle = f"import_echeancier_{pk}"
    if request.GET.get("recommencer"):
        request.session.pop(cle, None)
        return redirect("credit:importer", pk=pk)
    if request.method == "POST" and "fichier" in request.FILES:
        fichier = request.FILES["fichier"]
        if fichier.size > TAILLE_MAX_CSV:
            messages.error(request, "Le fichier dépasse 1 Mo.")
            return redirect("credit:importer", pk=pk)
        texte = decoder(fichier.read())
        try:
            lire_entetes(texte)
        except ErreurImport as erreur:
            messages.error(request, str(erreur))
            return redirect("credit:importer", pk=pk)
        request.session[cle] = texte
        return redirect("credit:importer", pk=pk)
    texte = request.session.get(cle)
    if texte is None:
        return render(request, "credit/import_fichier.html", {"pret": pret})
    form = ColonnesForm(lire_entetes(texte), request.POST or None)
    apercu = None
    if request.method == "POST" and form.is_valid():
        try:
            lues = lire_echeancier(texte, form.colonnes())
        except ErreurImport as erreur:
            form.add_error(None, str(erreur))
        else:
            if "importer" in request.POST:
                with transaction.atomic():
                    for e in lues:
                        Echeance.objects.update_or_create(
                            pret=pret, date=e.date,
                            defaults={"capital": e.capital, "interets": e.interets, "assurance": e.assurance},
                        )
                del request.session[cle]
                messages.success(request, f"{len(lues)} échéances importées.")
                return redirect(pret)
            apercu = {
                "lignes": lues[:12], "nombre": len(lues),
                "capital": sum(e.capital for e in lues), "interets": sum(e.interets for e in lues),
                "assurance": sum(e.assurance for e in lues),
            }
    return render(request, "credit/import_colonnes.html", {"pret": pret, "form": form, "apercu": apercu})
```

`credit/urls.py` :

```python
from django.urls import path

from . import views

app_name = "credit"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/importer/", views.importer, name="importer"),
]
```

Dans `config/urls.py`, ajouter `path("credit/", include("credit.urls")),` après `operations/`.

- [ ] **Step 4: Gabarits**

`templates/credit/liste.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Crédit{% endblock %}
{% block contenu %}
<header class="entete">
  <div><h1>Crédit</h1><p class="sous-titre">Les intérêts et l'assurance des échéances alimentent la ligne 250.</p></div>
  <a class="bouton principal" href="{% url 'credit:creer' %}">+ Nouveau prêt</a>
</header>
<div class="carte tableau">
<table>
  <thead><tr><th>Bien</th><th>Banque</th><th>Début</th><th class="montant">Capital emprunté</th></tr></thead>
  <tbody>
  {% for pret in prets %}
    <tr><td>{{ pret.bien.nom }}</td><td><a href="{{ pret.get_absolute_url }}">{{ pret.banque }}{% if pret.libelle %} — {{ pret.libelle }}{% endif %}</a></td><td>{{ pret.date_debut|date:"d/m/Y" }}</td><td class="montant">{{ pret.capital_emprunte|euros }}</td></tr>
  {% empty %}
    <tr><td colspan="4">Aucun prêt pour l'instant.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
```

`templates/credit/detail.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}{{ pret }}{% endblock %}
{% block contenu %}
<header class="entete">
  <div><h1>{{ pret.banque }}{% if pret.libelle %} — {{ pret.libelle }}{% endif %}</h1><p class="sous-titre">{{ pret.bien.nom }} · {{ pret.capital_emprunte|euros }} empruntés le {{ pret.date_debut|date:"d/m/Y" }}</p></div>
  <div class="actions">
    <a class="bouton" href="{% url 'credit:modifier' pret.pk %}">Modifier</a>
    <a class="bouton principal" href="{% url 'credit:importer' pret.pk %}">Importer un échéancier</a>
  </div>
</header>
<div class="carte tableau">
<table>
  <thead><tr><th>Année</th><th class="montant">Capital (non déductible)</th><th class="montant">Intérêts</th><th class="montant">Assurance</th><th class="montant">Frais</th><th class="montant">Déductible (ligne 250)</th></tr></thead>
  <tbody>
  {% for a in annees %}
    <tr><td>{{ a.annee }}</td><td class="montant">{{ a.capital|euros }}</td><td class="montant">{{ a.interets|euros }}</td><td class="montant">{{ a.assurance|euros }}</td><td class="montant">{{ a.frais|euros }}</td><td class="montant"><strong>{{ a.deductible|euros }}</strong></td></tr>
  {% empty %}
    <tr><td colspan="6">Aucune échéance : importez le tableau d'amortissement de la banque.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% if echeances %}
<details class="carte"><summary>Détail des {{ echeances|length }} échéances</summary>
<table>
  <thead><tr><th>Date</th><th class="montant">Capital</th><th class="montant">Intérêts</th><th class="montant">Assurance</th></tr></thead>
  <tbody>{% for e in echeances %}<tr><td>{{ e.date|date:"d/m/Y" }}</td><td class="montant">{{ e.capital|euros }}</td><td class="montant">{{ e.interets|euros }}</td><td class="montant">{{ e.assurance|euros }}</td></tr>{% endfor %}</tbody>
</table>
</details>
{% endif %}
{% endblock %}
```

`templates/credit/import_fichier.html` :

```html
{% extends "base.html" %}
{% block titre %}Importer un échéancier{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>Importer un échéancier</h1><p class="sous-titre">{{ pret }}</p></div></header>
<form method="post" enctype="multipart/form-data" class="carte formulaire">
  {% csrf_token %}
  <p>Exportez le tableau d'amortissement depuis le site de votre banque au format CSV, puis choisissez le fichier. Vous indiquerez ensuite quelles colonnes correspondent à la date, au capital, aux intérêts et à l'assurance.</p>
  <div class="champ"><label for="fichier">Fichier CSV (1 Mo maximum)</label><input id="fichier" type="file" name="fichier" accept=".csv,text/csv" required></div>
  <div class="actions"><button class="bouton principal" type="submit">Continuer</button><a class="bouton" href="{{ pret.get_absolute_url }}">Annuler</a></div>
</form>
{% endblock %}
```

`templates/credit/import_colonnes.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Importer un échéancier{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>Correspondance des colonnes</h1><p class="sous-titre">{{ pret }}</p></div></header>
<form method="post" class="carte formulaire">
  {% csrf_token %}
  {{ form }}
  <div class="actions">
    <button class="bouton" type="submit" name="apercu" value="1">Aperçu</button>
    <button class="bouton principal" type="submit" name="importer" value="1">Importer</button>
    <a href="?recommencer=1">Choisir un autre fichier</a>
  </div>
</form>
{% if apercu %}
<section class="carte">
  <h2>Aperçu : {{ apercu.nombre }} échéances</h2>
  <p>Capital {{ apercu.capital|euros }} · intérêts {{ apercu.interets|euros }} · assurance {{ apercu.assurance|euros }}</p>
  <table>
    <thead><tr><th>Date</th><th class="montant">Capital</th><th class="montant">Intérêts</th><th class="montant">Assurance</th></tr></thead>
    <tbody>{% for e in apercu.lignes %}<tr><td>{{ e.date|date:"d/m/Y" }}</td><td class="montant">{{ e.capital|euros }}</td><td class="montant">{{ e.interets|euros }}</td><td class="montant">{{ e.assurance|euros }}</td></tr>{% endfor %}</tbody>
  </table>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `124 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(credit): prêts, échéances et import CSV du tableau d'amortissement"
```

---

### Task 10: Paramètres annuels, copropriété, déficits ; contrôle d'accès global

**Files:**
- Create: `fiscalite/{__init__,apps,models,forms,views,urls,admin}.py`, `fiscalite/migrations/__init__.py`, `fiscalite/migrations/0001_initial.py` (générée), `fiscalite/migrations/0002_parametres.py`, `templates/fiscalite/{copropriete,deficits}.html`
- Modify: `config/settings.py` (`"fiscalite",`), `config/urls.py` (`path("fiscalite/", include("fiscalite.urls")),`)
- Test: `tests/fiscalite/__init__.py`, `tests/fiscalite/test_saisie.py`, `tests/test_securite.py`

**Interfaces:**
- Consumes: `fiscal.ParametresAnnuels`, `biens.Bien`, `MontantField`.
- Produces: `ParametresAnnuels` (`annee` unique, `plafond_imputation`, `forfait_gestion`, `taux_prelevements_sociaux`, `tmi`, `plafonds_pinel_m2` (JSON zone → centimes/m²), `commentaire` ; `vers_fiscal()`), lignes 2024 à 2026 créées par migration ; `DecompteCopropriete` (`bien`, `annee`, `part_non_deductible`, `commentaire`, unique `(bien, annee)` : part non déductible du décompte de l'année N, reportée en ligne 230 de N+1) ; `DeficitAnterieur` (`annee_origine` unique, `montant` : solde restant au 1er janvier de la première année gérée) ; `Configuration` singleton (`premiere_annee`, défaut 2025 ; `Configuration.charger()`) ; URLs `fiscalite:copropriete`, `fiscalite:modifier_decompte`, `fiscalite:supprimer_decompte`, `fiscalite:deficits`, `fiscalite:supprimer_deficit`.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/fiscalite/__init__.py` vide. `tests/fiscalite/test_saisie.py` :

```python
import pytest
from django.urls import reverse

import fiscal
from fiscalite.models import Configuration, DecompteCopropriete, DeficitAnterieur, ParametresAnnuels
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def test_parametres_initiaux():
    p = ParametresAnnuels.objects.get(annee=2025)
    assert p.vers_fiscal() == fiscal.ParametresAnnuels(
        annee=2025, plafond_imputation_revenu_global=1_070_000, forfait_gestion_par_local=2_000
    )
    assert ParametresAnnuels.objects.filter(annee__in=[2024, 2025, 2026]).count() == 3


def test_saisie_d_un_decompte_de_copropriete(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("fiscalite:copropriete"), {
        "bien": b.pk, "annee": "2024", "part_non_deductible": "210", "commentaire": "",
    })
    assert r.status_code == 302
    assert DecompteCopropriete.objects.get().part_non_deductible == 21_000


def test_decompte_en_double_refuse(client_verifie):
    b = creer_bien()
    DecompteCopropriete.objects.create(bien=b, annee=2024, part_non_deductible=1)
    r = client_verifie.post(reverse("fiscalite:copropriete"), {
        "bien": b.pk, "annee": "2024", "part_non_deductible": "210", "commentaire": "",
    })
    assert r.status_code == 200
    assert DecompteCopropriete.objects.count() == 1


def test_deficit_doit_etre_anterieur_a_la_premiere_annee(client_verifie):
    r = client_verifie.post(reverse("fiscalite:deficits"), {
        "deficit-annee_origine": "2025", "deficit-montant": "2 400", "deficit": "1",
    })
    assert r.status_code == 200
    assert "antérieur" in r.content.decode()
    assert not DeficitAnterieur.objects.exists()


def test_changer_la_premiere_annee_puis_saisir_un_deficit(client_verifie):
    client_verifie.post(reverse("fiscalite:deficits"), {"config-premiere_annee": "2024", "configuration": "1"})
    assert Configuration.charger().premiere_annee == 2024
    r = client_verifie.post(reverse("fiscalite:deficits"), {
        "deficit-annee_origine": "2022", "deficit-montant": "2 400", "deficit": "1",
    })
    assert r.status_code == 302
    assert DeficitAnterieur.objects.get().montant == 240_000
```

`tests/test_securite.py` :

```python
import pytest

pytestmark = pytest.mark.django_db
URLS = [
    "/", "/biens/", "/biens/nouveau/", "/operations/", "/operations/nouvelle/", "/credit/",
    "/fiscalite/copropriete/", "/fiscalite/deficits/", "/admin/",
]


@pytest.mark.parametrize("url", URLS)
def test_anonyme_redirige_vers_une_connexion(client, url):
    r = client.get(url)
    assert r.status_code == 302
    assert "connexion" in r.url or "login" in r.url


@pytest.mark.parametrize("url", URLS)
def test_connecte_sans_double_authentification_redirige(client, utilisateur, url):
    client.force_login(utilisateur)
    r = client.get(url)
    assert r.status_code == 302
    assert r.url.startswith("/compte/double-authentification/")
```

Run: `.venv/Scripts/python.exe -m pytest tests/fiscalite tests/test_securite.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscalite'`.

- [ ] **Step 2: Modèles et migrations**

`fiscalite/apps.py` (`FiscaliteConfig`, `verbose_name = "Fiscalité"`), fichiers `__init__.py` vides. `fiscalite/models.py` :

```python
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

import fiscal
from biens.models import Bien


class ParametresAnnuels(models.Model):
    annee = models.PositiveSmallIntegerField("année", unique=True)
    plafond_imputation = models.BigIntegerField("plafond d'imputation sur le revenu global (centimes)", default=1_070_000)
    forfait_gestion = models.BigIntegerField("forfait de gestion par local, ligne 222 (centimes)", default=2_000)
    taux_prelevements_sociaux = models.DecimalField(
        "taux des prélèvements sociaux (%)", max_digits=5, decimal_places=2, default=Decimal("17.20")
    )
    tmi = models.DecimalField("tranche marginale d'imposition du foyer (%)", max_digits=5, decimal_places=2, default=Decimal("30"))
    plafonds_pinel_m2 = models.JSONField(
        "plafonds de loyer Pinel (centimes par m², par zone)", default=dict, blank=True,
        help_text='Exemple : {"A": 1349, "B1": 1087} — à reprendre du BOFiP de l\'année.',
    )
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        ordering = ["-annee"]
        verbose_name = "paramètres annuels"
        verbose_name_plural = "paramètres annuels"

    def __str__(self):
        return f"Paramètres {self.annee}"

    def vers_fiscal(self) -> fiscal.ParametresAnnuels:
        return fiscal.ParametresAnnuels(
            annee=self.annee, plafond_imputation_revenu_global=self.plafond_imputation,
            forfait_gestion_par_local=self.forfait_gestion,
        )


class Configuration(models.Model):
    premiere_annee = models.PositiveSmallIntegerField("première année gérée par l'application", default=2025)

    class Meta:
        verbose_name = "configuration"

    def __str__(self):
        return "Configuration"

    @classmethod
    def charger(cls) -> "Configuration":
        configuration, _ = cls.objects.get_or_create(pk=1)
        return configuration


class DecompteCopropriete(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="decomptes")
    annee = models.PositiveSmallIntegerField("année du décompte")
    part_non_deductible = models.BigIntegerField(
        "part non déductible des provisions (centimes)",
        help_text="Charges récupérables et dépenses non déductibles indiquées par le syndic.",
    )
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        ordering = ["-annee", "bien__nom"]
        verbose_name = "décompte de copropriété"
        constraints = [models.UniqueConstraint(fields=["bien", "annee"], name="decompte_unique_par_annee")]

    def __str__(self):
        return f"Décompte {self.annee} — {self.bien}"


class DeficitAnterieur(models.Model):
    annee_origine = models.PositiveSmallIntegerField("année d'origine", unique=True)
    montant = models.BigIntegerField("solde restant à imputer (centimes)", validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["annee_origine"]
        verbose_name = "déficit antérieur"

    def __str__(self):
        return f"Déficit {self.annee_origine}"

    def clean(self):
        premiere = Configuration.charger().premiere_annee
        if self.annee_origine is not None and self.annee_origine >= premiere:
            raise ValidationError(
                {"annee_origine": f"Le déficit doit être antérieur à la première année gérée ({premiere})."}
            )
```

Ajouter `"fiscalite",` à `INSTALLED_APPS`.

Run: `DJANGO_DEBUG=1 .venv/Scripts/python.exe manage.py makemigrations fiscalite`
Expected: `Migrations for 'fiscalite': fiscalite/migrations/0001_initial.py`

`fiscalite/migrations/0002_parametres.py` :

```python
from django.db import migrations


def creer(apps, schema_editor):
    ParametresAnnuels = apps.get_model("fiscalite", "ParametresAnnuels")
    for annee in (2024, 2025, 2026):
        ParametresAnnuels.objects.get_or_create(
            annee=annee, defaults={"commentaire": "Valeurs par défaut : vérifier la TMI et les plafonds Pinel."}
        )


class Migration(migrations.Migration):
    dependencies = [("fiscalite", "0001_initial")]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
```

`fiscalite/admin.py` :

```python
from django.contrib import admin

from .models import Configuration, ParametresAnnuels

admin.site.register(ParametresAnnuels)
admin.site.register(Configuration)
```

- [ ] **Step 3: Formulaires, vues, routes**

`fiscalite/forms.py` :

```python
from django import forms

from commun.forms import MontantField

from .models import Configuration, DecompteCopropriete, DeficitAnterieur


class DecompteForm(forms.ModelForm):
    part_non_deductible = MontantField(label="Part non déductible (€)", minimum=0)

    class Meta:
        model = DecompteCopropriete
        fields = ["bien", "annee", "part_non_deductible", "commentaire"]
        widgets = {"commentaire": forms.Textarea(attrs={"rows": 2})}


class DeficitForm(forms.ModelForm):
    montant = MontantField(label="Solde restant à imputer (€)")

    class Meta:
        model = DeficitAnterieur
        fields = ["annee_origine", "montant"]


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = Configuration
        fields = ["premiere_annee"]
```

`fiscalite/views.py` :

```python
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ConfigurationForm, DecompteForm, DeficitForm
from .models import Configuration, DecompteCopropriete, DeficitAnterieur


def copropriete(request):
    form = DecompteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Décompte enregistré.")
        return redirect("fiscalite:copropriete")
    decomptes = DecompteCopropriete.objects.select_related("bien")
    return render(request, "fiscalite/copropriete.html", {"form": form, "decomptes": decomptes})


def modifier_decompte(request, pk):
    decompte = get_object_or_404(DecompteCopropriete, pk=pk)
    form = DecompteForm(request.POST or None, instance=decompte)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Décompte enregistré.")
        return redirect("fiscalite:copropriete")
    return render(request, "commun/formulaire.html", {
        "form": form, "titre": "Modifier le décompte", "retour": reverse("fiscalite:copropriete"),
        "suppression": reverse("fiscalite:supprimer_decompte", args=[pk]),
    })


@require_POST
def supprimer_decompte(request, pk):
    get_object_or_404(DecompteCopropriete, pk=pk).delete()
    messages.success(request, "Décompte supprimé.")
    return redirect("fiscalite:copropriete")


def deficits(request):
    configuration = Configuration.charger()
    form_config = ConfigurationForm(
        request.POST if "configuration" in request.POST else None, instance=configuration, prefix="config"
    )
    form_deficit = DeficitForm(request.POST if "deficit" in request.POST else None, prefix="deficit")
    if request.method == "POST":
        if "configuration" in request.POST and form_config.is_valid():
            form_config.save()
            messages.success(request, "Première année gérée enregistrée.")
            return redirect("fiscalite:deficits")
        if "deficit" in request.POST and form_deficit.is_valid():
            form_deficit.save()
            messages.success(request, "Déficit enregistré.")
            return redirect("fiscalite:deficits")
    return render(request, "fiscalite/deficits.html", {
        "configuration": configuration, "form_config": form_config, "form_deficit": form_deficit,
        "deficits": DeficitAnterieur.objects.all(),
    })


@require_POST
def supprimer_deficit(request, pk):
    get_object_or_404(DeficitAnterieur, pk=pk).delete()
    messages.success(request, "Déficit supprimé.")
    return redirect("fiscalite:deficits")
```

`fiscalite/urls.py` :

```python
from django.urls import path

from . import views

app_name = "fiscalite"

urlpatterns = [
    path("copropriete/", views.copropriete, name="copropriete"),
    path("copropriete/<int:pk>/", views.modifier_decompte, name="modifier_decompte"),
    path("copropriete/<int:pk>/supprimer/", views.supprimer_decompte, name="supprimer_decompte"),
    path("deficits/", views.deficits, name="deficits"),
    path("deficits/<int:pk>/supprimer/", views.supprimer_deficit, name="supprimer_deficit"),
]
```

Dans `config/urls.py`, ajouter `path("fiscalite/", include("fiscalite.urls")),` après `credit/`.

- [ ] **Step 4: Gabarits**

`templates/fiscalite/copropriete.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Copropriété{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>Copropriété</h1><p class="sous-titre">Les appels de fonds se saisissent comme des opérations (ligne 229). Ici, la part non déductible indiquée par le décompte annuel du syndic : elle est reprise en ligne 230 l'année suivante.</p></div></header>
<div class="grille">
  <form method="post" class="carte formulaire">
    {% csrf_token %}
    <h2>Nouveau décompte</h2>
    {{ form }}
    <div class="actions"><button class="bouton principal" type="submit">Enregistrer</button></div>
  </form>
  <div class="carte tableau">
    <table>
      <thead><tr><th>Année</th><th>Bien</th><th class="montant">Part non déductible</th><th>Reprise</th></tr></thead>
      <tbody>
      {% for d in decomptes %}
        <tr><td><a href="{% url 'fiscalite:modifier_decompte' d.pk %}">{{ d.annee }}</a></td><td>{{ d.bien.nom }}</td><td class="montant">{{ d.part_non_deductible|euros }}</td><td>ligne 230 de {{ d.annee|add:1 }}</td></tr>
      {% empty %}
        <tr><td colspan="4">Aucun décompte saisi.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

`templates/fiscalite/deficits.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Déficits{% endblock %}
{% block contenu %}
<header class="entete"><div><h1>Déficits fonciers antérieurs</h1><p class="sous-titre">Saisissez une fois les déficits restant à imputer au 1er janvier {{ configuration.premiere_annee }} (voir votre dernier avis d'imposition). L'application les tient à jour ensuite.</p></div></header>
<div class="grille">
  <form method="post" class="carte formulaire">
    {% csrf_token %}
    <h2>Première année gérée</h2>
    {{ form_config }}
    <div class="actions"><button class="bouton" type="submit" name="configuration" value="1">Enregistrer</button></div>
  </form>
  <form method="post" class="carte formulaire">
    {% csrf_token %}
    <h2>Ajouter un déficit</h2>
    {{ form_deficit }}
    <div class="actions"><button class="bouton principal" type="submit" name="deficit" value="1">Ajouter</button></div>
  </form>
</div>
<div class="carte tableau">
  <table>
    <thead><tr><th>Année d'origine</th><th class="montant">Solde au 1er janvier {{ configuration.premiere_annee }}</th><th>Dernière année d'imputation</th><th><span class="sr">Actions</span></th></tr></thead>
    <tbody>
    {% for d in deficits %}
      <tr><td>{{ d.annee_origine }}</td><td class="montant">{{ d.montant|euros }}</td><td>{{ d.annee_origine|add:10 }}</td>
        <td><form method="post" action="{% url 'fiscalite:supprimer_deficit' d.pk %}">{% csrf_token %}<button class="lien" type="submit">Supprimer</button></form></td></tr>
    {% empty %}
      <tr><td colspan="4">Aucun déficit antérieur.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `147 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(fiscalite): paramètres annuels, copropriété, déficits et contrôle d'accès"
```

---

### Task 11: Service de calcul (base → moteur fiscal)

**Files:**
- Create: `fiscalite/services.py`
- Test: `tests/fiscalite/test_services.py`

**Interfaces:**
- Consumes: modèles de Tasks 4, 6, 9, 10 ; `fiscal.calculateur_pour`, `fiscal.REGIME_FONCIER_REEL`, `fiscal.Operation`, `fiscal.Nature`, `fiscal.DeficitReportable`.
- Produces: `ParametresManquants(Exception)` ; `ContexteFiscal(annee, biens, operations, params, sources: dict[int, str])` ; `contexte_fiscal(annee) -> ContexteFiscal` (opérations de la base + une opération ligne 250 par échéance avec intérêts/assurance/frais > 0 + une opération ligne 230 par décompte de l'année précédente ; identifiants synthétiques à partir de `ID_SYNTHETIQUE = 10**12`) ; `deficits_au_debut_de(annee) -> tuple[DeficitReportable, ...]` (enchaîne les calculs depuis `Configuration.premiere_annee`) ; `calculer_annee(annee) -> tuple[ResultatFoncier, ContexteFiscal]`. Utilisé par le plan 3.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/fiscalite/test_services.py`

```python
from datetime import date

import pytest

from credit.models import Echeance, Pret
from fiscal import DeficitReportable as DR
from fiscalite.models import Configuration, DecompteCopropriete, DeficitAnterieur, ParametresAnnuels
from fiscalite.services import ParametresManquants, calculer_annee, deficits_au_debut_de
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def preparer_exemple_2025():
    config = Configuration.charger()
    config.premiere_annee = 2025
    config.save()
    t2, t3 = creer_bien("T2 Les Tilleuls"), creer_bien("T3 Centre")
    for bien, montants in ((t2, (744_000, 52_100, 14_800, 0, 81_200, 96_000)),
                           (t3, (936_000, 65_500, 17_500, 640_000, 104_500, 132_000))):
        loyer, honoraires, assurance, travaux, taxe, copro = montants
        creer_operation(bien, "loyer", loyer, date(2025, 6, 5))
        creer_operation(bien, "honoraires", honoraires, date(2025, 12, 31))
        creer_operation(bien, "assurance-pno", assurance, date(2025, 5, 2))
        if travaux:
            creer_operation(bien, "travaux", travaux, date(2025, 3, 12))
        creer_operation(bien, "taxe-fonciere", taxe, date(2025, 10, 15))
        creer_operation(bien, "provisions-copro", copro, date(2025, 1, 10))
        creer_operation(bien, "teom", 16_800, date(2025, 10, 15))
    for bien, interets in ((t2, 200_000), (t3, 377_000)):
        pret = Pret.objects.create(bien=bien, banque="Banque", capital_emprunte=1, date_debut=date(2015, 1, 5))
        Echeance.objects.create(pret=pret, date=date(2025, 6, 5), capital=61_245, interets=interets, assurance=18_000)
    DecompteCopropriete.objects.create(bien=t2, annee=2024, part_non_deductible=21_000)
    DecompteCopropriete.objects.create(bien=t3, annee=2024, part_non_deductible=29_000)
    DeficitAnterieur.objects.create(annee_origine=2022, montant=240_000)
    DeficitAnterieur.objects.create(annee_origine=2023, montant=115_000)


def test_exemple_complet_depuis_la_base():
    preparer_exemple_2025()
    resultat, contexte = calculer_annee(2025)
    assert [b.resultat for b in resultat.biens] == [300_900, -391_500]
    assert resultat.deficit.case_4bc == 90_600
    assert resultat.deficit.case_4bd == 355_000


def test_echeances_et_decomptes_tracables():
    preparer_exemple_2025()
    resultat, contexte = calculer_annee(2025)
    ligne_250 = resultat.biens[0].lignes["250"]
    assert ligne_250.montant == 218_000
    assert "échéance" in contexte.sources[ligne_250.explication.operation_ids[0]]
    ligne_230 = resultat.biens[0].lignes["230"]
    assert ligne_230.montant == 21_000
    assert "décompte 2024" in contexte.sources[ligne_230.explication.operation_ids[0]]


def test_deficits_tenus_a_jour_d_une_annee_sur_l_autre():
    config = Configuration.charger()
    config.premiere_annee = 2024
    config.save()
    DeficitAnterieur.objects.create(annee_origine=2022, montant=240_000)
    creer_operation(creer_bien(), "loyer", 100_000, date(2024, 6, 5))
    assert deficits_au_debut_de(2025) == (DR(2022, 142_000),)


def test_parametres_absents():
    ParametresAnnuels.objects.filter(annee=2025).delete()
    with pytest.raises(ParametresManquants, match="2025"):
        calculer_annee(2025)


def test_annee_anterieure_a_la_premiere_annee_geree():
    with pytest.raises(ValueError, match="première année"):
        calculer_annee(2020)
```

Run: `.venv/Scripts/python.exe -m pytest tests/fiscalite/test_services.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscalite.services'`.

- [ ] **Step 2: Implémenter** — `fiscalite/services.py`

```python
"""Conversion des données de la base vers le moteur `fiscal`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import count

import fiscal
from biens.models import Bien
from credit.models import Echeance
from operations.models import Operation

from .models import Configuration, DecompteCopropriete, DeficitAnterieur, ParametresAnnuels

ID_SYNTHETIQUE = 10**12


class ParametresManquants(Exception):
    pass


@dataclass(frozen=True)
class ContexteFiscal:
    annee: int
    biens: tuple[fiscal.Bien, ...]
    operations: tuple[fiscal.Operation, ...]
    params: fiscal.ParametresAnnuels
    sources: dict[int, str]


def contexte_fiscal(annee: int) -> ContexteFiscal:
    parametres = ParametresAnnuels.objects.filter(annee=annee).first()
    if parametres is None:
        raise ParametresManquants(
            f"Paramètres fiscaux {annee} absents : créez-les dans Paramètres avant de lancer le calcul."
        )
    operations: list[fiscal.Operation] = []
    sources: dict[int, str] = {}
    for o in Operation.objects.filter(date_paiement__year=annee).select_related("bien", "categorie"):
        operations.append(o.vers_fiscal())
        sources[o.pk] = f"{o.date_paiement:%d/%m/%Y} — {o.bien.nom} — {o.libelle}"

    identifiants = count(ID_SYNTHETIQUE)
    for e in Echeance.objects.filter(date__year=annee).select_related("pret__bien"):
        if e.deductible <= 0:
            continue
        i = next(identifiants)
        operations.append(fiscal.Operation(
            id=i, bien_id=e.pret.bien_id, date_paiement=e.date, montant=e.deductible,
            nature=fiscal.Nature.INTERETS, ligne_2044="250", libelle=f"Échéance du {e.date:%d/%m/%Y}",
        ))
        sources[i] = f"{e.date:%d/%m/%Y} — {e.pret.bien.nom} — échéance {e.pret.banque} (intérêts et assurance)"
    for d in DecompteCopropriete.objects.filter(annee=annee - 1, part_non_deductible__gt=0).select_related("bien"):
        i = next(identifiants)
        operations.append(fiscal.Operation(
            id=i, bien_id=d.bien_id, date_paiement=date(annee, 1, 1), montant=d.part_non_deductible,
            nature=fiscal.Nature.CHARGE_DEDUCTIBLE, ligne_2044="230", libelle=f"Régularisation copropriété {d.annee}",
        ))
        sources[i] = f"{d.bien.nom} — décompte {d.annee} du syndic (part non déductible)"

    return ContexteFiscal(
        annee=annee,
        biens=tuple(b.vers_fiscal() for b in Bien.objects.all()),
        operations=tuple(operations),
        params=parametres.vers_fiscal(),
        sources=sources,
    )


def _calculer(annee: int, deficits) -> tuple[fiscal.ResultatFoncier, ContexteFiscal]:
    contexte = contexte_fiscal(annee)
    calculateur = fiscal.calculateur_pour(fiscal.REGIME_FONCIER_REEL)
    resultat = calculateur.calculer(annee, contexte.biens, contexte.operations, deficits, contexte.params)
    return resultat, contexte


def deficits_au_debut_de(annee: int) -> tuple[fiscal.DeficitReportable, ...]:
    premiere = Configuration.charger().premiere_annee
    if annee < premiere:
        raise ValueError(f"{annee} est antérieure à la première année gérée ({premiere}).")
    stock = tuple(fiscal.DeficitReportable(d.annee_origine, d.montant) for d in DeficitAnterieur.objects.all())
    for a in range(premiere, annee):
        stock = _calculer(a, stock)[0].deficit.deficits_apres
    return stock


def calculer_annee(annee: int) -> tuple[fiscal.ResultatFoncier, ContexteFiscal]:
    return _calculer(annee, deficits_au_debut_de(annee))
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `152 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(fiscalite): service de calcul depuis la base"
```

---

### Task 12: Données de démonstration et mode d'emploi local

**Files:**
- Create: `fiscalite/management/__init__.py`, `fiscalite/management/commands/__init__.py`, `fiscalite/management/commands/seed_demo.py`, `README.md`
- Test: `tests/fiscalite/test_seed_demo.py`

**Interfaces:**
- Consumes: tous les modèles ; `calculer_annee`.
- Produces: commande `manage.py seed_demo` (base sans bien uniquement ; crée les données fictives de la maquette pour 2025).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/fiscalite/test_seed_demo.py`

```python
import pytest
from django.core.management import CommandError, call_command

from fiscalite.services import calculer_annee

pytestmark = pytest.mark.django_db


def test_donnees_de_demonstration_retrouvent_la_maquette():
    call_command("seed_demo")
    resultat, _ = calculer_annee(2025)
    assert [b.resultat for b in resultat.biens] == [300_900, -391_500]
    assert resultat.deficit.case_4bc == 90_600
    assert resultat.deficit.case_4bd == 355_000


def test_refuse_une_base_non_vide():
    call_command("seed_demo")
    with pytest.raises(CommandError, match="déjà des biens"):
        call_command("seed_demo")
```

Run: `.venv/Scripts/python.exe -m pytest tests/fiscalite/test_seed_demo.py -q`
Expected: FAIL — `CommandError: Unknown command: 'seed_demo'`.

- [ ] **Step 2: Implémenter** — fichiers `__init__.py` vides, puis `fiscalite/management/commands/seed_demo.py` :

```python
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from biens.models import Bail, Bien, EngagementPinel, Locataire, PeriodePinel
from credit.models import Echeance, Pret
from fiscalite.models import Configuration, DecompteCopropriete, DeficitAnterieur
from operations.models import Categorie, Operation


class Command(BaseCommand):
    help = "Crée des données fictives de démonstration (base sans bien uniquement)."

    @transaction.atomic
    def handle(self, *args, **options):
        if Bien.objects.exists():
            raise CommandError("La base contient déjà des biens : seed_demo ne s'exécute que sur une base vide.")
        configuration = Configuration.charger()
        configuration.premiere_annee = 2025
        configuration.save()

        t2 = Bien.objects.create(
            nom="T2 Les Tilleuls", adresse="[Adresse fictive]", surface_habitable=Decimal("45"),
            surface_annexes=Decimal("7"), date_acquisition=date(2014, 11, 20), prix_revient=16_800_000,
        )
        t3 = Bien.objects.create(
            nom="T3 Centre", adresse="[Adresse fictive]", surface_habitable=Decimal("62"),
            date_acquisition=date(2019, 6, 3), prix_revient=19_500_000,
        )
        pinel = EngagementPinel.objects.create(
            bien=t2, date_mise_en_location=date(2015, 1, 1), duree_annees=12, zone="A",
            prix_revient=16_800_000, surface_habitable=Decimal("45"),
        )
        PeriodePinel.objects.create(engagement=pinel, annee_debut=2015, annee_fin=2023, taux_annuel=Decimal("2"))
        PeriodePinel.objects.create(engagement=pinel, annee_debut=2024, annee_fin=2026, taux_annuel=Decimal("1"))
        for bien, nom, loyer in ((t2, "Locataire A (fictif)", 62_000), (t3, "Locataire B (fictif)", 78_000)):
            Bail.objects.create(
                bien=bien, locataire=Locataire.objects.create(nom=nom), date_debut=date(2023, 9, 1),
                loyer_hc=loyer, provision_charges=4_000,
            )

        categories = {c.code: c for c in Categorie.objects.all()}

        def operation(bien, code, montant, jour, libelle):
            Operation.objects.create(
                bien=bien, categorie=categories[code], date_paiement=jour, montant=montant, libelle=libelle
            )

        for mois in range(1, 13):
            operation(t2, "loyer", 62_000, date(2025, mois, 5), f"Loyer {mois:02d}/2025")
            operation(t3, "loyer", 78_000, date(2025, mois, 5), f"Loyer {mois:02d}/2025")
        for bien, honoraires, assurance, taxe, appel in (
            (t2, 52_100, 14_800, 81_200, 24_000), (t3, 65_500, 17_500, 104_500, 33_000)
        ):
            operation(bien, "honoraires", honoraires, date(2025, 12, 31), "Honoraires d'agence 2025")
            operation(bien, "assurance-pno", assurance, date(2025, 5, 2), "Assurance propriétaire non occupant")
            operation(bien, "taxe-fonciere", taxe, date(2025, 10, 15), "Taxe foncière 2025 (hors TEOM)")
            operation(bien, "teom", 16_800, date(2025, 10, 15), "Taxe d'enlèvement des ordures ménagères")
            for mois in (1, 4, 7, 10):
                operation(bien, "provisions-copro", appel, date(2025, mois, 10), f"Appel de fonds {mois:02d}/2025")
        operation(t3, "travaux", 420_000, date(2025, 3, 12), "Rénovation de la salle d'eau")
        operation(t3, "travaux", 220_000, date(2025, 9, 20), "Remplacement de la cuisine")

        for bien, interets in ((t2, 218_000), (t3, 395_000)):
            pret = Pret.objects.create(
                bien=bien, banque="Banque fictive", capital_emprunte=15_000_000, date_debut=date(2015, 1, 5)
            )
            mensuel = interets // 12
            for mois in range(1, 13):
                reste = interets - mensuel * 12 if mois == 12 else 0
                Echeance.objects.create(pret=pret, date=date(2025, mois, 5), capital=61_245, interets=mensuel + reste)

        DecompteCopropriete.objects.create(bien=t2, annee=2024, part_non_deductible=21_000, commentaire="Fictif")
        DecompteCopropriete.objects.create(bien=t3, annee=2024, part_non_deductible=29_000, commentaire="Fictif")
        DeficitAnterieur.objects.create(annee_origine=2022, montant=240_000)
        DeficitAnterieur.objects.create(annee_origine=2023, montant=115_000)
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées (2 biens, année 2025)."))
```

`README.md` :

```markdown
# Gestion de patrimoine locatif

Application personnelle de suivi des locations vides (régime réel, déclaration 2044), installée sur un Synology.

## Lancer l'application sur le PC (développement)

Depuis Git Bash, à la racine du projet :

    py -3.14 -m venv .venv
    .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
    export DJANGO_DEBUG=1
    .venv/Scripts/python.exe manage.py migrate
    .venv/Scripts/python.exe manage.py createsuperuser
    .venv/Scripts/python.exe manage.py seed_demo      # facultatif : données fictives 2025
    .venv/Scripts/python.exe manage.py runserver

Ouvrir http://127.0.0.1:8000/, se connecter, puis scanner le QR code avec une application
d'authentification (double authentification obligatoire).

La base SQLite et les justificatifs sont dans `var/` (ignoré par git).

## Tests

    .venv/Scripts/python.exe -m pytest -q
    .venv/Scripts/python.exe -m ruff check .

## Avertissement

L'application aide à préparer la déclaration ; vérifiez chaque année les montants avec la notice 2044
et les paramètres fiscaux (Paramètres → Paramètres annuels).
```

- [ ] **Step 3: Vérifier le succès et la commande réelle**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `154 passed`, `All checks passed!`

Run: `DJANGO_DEBUG=1 PATRIMOINE_DATA_DIR="$(mktemp -d)" bash -c '.venv/Scripts/python.exe manage.py migrate -v 0 && .venv/Scripts/python.exe manage.py seed_demo'`
Expected: `Données de démonstration créées (2 biens, année 2025).`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(fiscalite): données de démonstration et mode d'emploi local"
```
