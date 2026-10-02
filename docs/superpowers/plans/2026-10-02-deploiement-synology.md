# Déploiement sur Synology (plan 4/4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'application installable sur le Synology du propriétaire, sans GitHub : réglages de production, enrôlement de la double authentification protégé par un code d'installation, création du compte au premier démarrage, sauvegarde quotidienne de la base, image Docker construite par Container Manager à partir d'une archive du projet, guide d'installation pas à pas.

**Architecture:** Un conteneur unique (Python 3.13 slim, Gunicorn, WhiteNoise pour les fichiers statiques), construit sur le NAS par Container Manager à partir de `docker-compose.yml` (`build: .`). Données dans `./data` (base SQLite, justificatifs, sauvegardes) à côté du projet sur le NAS. Le port du conteneur n'écoute que sur `127.0.0.1:8085` ; le reverse proxy de DSM publie `https://patrimoine.<domaine>`. Le point d'entrée applique les migrations, crée le compte si besoin, puis lance Gunicorn sous un utilisateur non privilégié.

**Tech Stack:** Django 5.2, gunicorn, whitenoise, Docker (Container Manager DSM 7.2), pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-02-gestion-patrimoine-design.md` (section 7). Écart volontaire décidé avec le propriétaire : pas de GitHub ni de ghcr.io (connexion GitHub impossible depuis le PC) ; l'image est construite sur le NAS à partir d'une archive ZIP copiée par File Station.

## Global Constraints

- Aucun secret dans le dépôt ni dans l'archive : `.env`, `var/`, `data/`, `.venv/` exclus (`.gitignore`, `.dockerignore`, `git archive`).
- Production : `DEBUG` faux, `DJANGO_SECRET_KEY` obligatoire, cookies `Secure`, HSTS, `SECURE_PROXY_SSL_HEADER` (le port du conteneur n'est joignable que depuis le NAS lui-même).
- `manage.py check --deploy --fail-level WARNING` passe avec des réglages de production ; tout avertissement mis en sourdine l'est avec un commentaire qui explique pourquoi.
- L'enrôlement TOTP (QR code) n'est possible en production qu'après saisie du code d'installation défini dans `.env` (`PATRIMOINE_CODE_INSTALLATION`) ; sans ce code, l'enrôlement est fermé.
- Le processus web tourne sous un utilisateur non root dans le conteneur.
- Docker n'est pas installé sur le PC : les fichiers Docker sont vérifiés par des tests de contenu ; la construction réelle se fait sur le NAS en suivant le guide.
- Textes en français ; `ruff check --fix .` propre (line-length 120) ; commandes depuis `E:/Projet-Gestion-Patrimoine` avec `.venv/Scripts/python.exe` ; les fichiers de plus de quelques lignes s'écrivent avec l'outil d'écriture de fichiers.

## Review Focus

- Compte connecté sans appareil TOTP en production, sans connaître le code d'installation → jamais de QR code affiché (tests Task 2).
- Redémarrage du conteneur alors que le compte existe déjà → le mot de passe n'est pas écrasé par celui du `.env` (test Task 3).
- Sauvegarde lancée deux fois dans la même seconde, ou plus de 30 sauvegardes présentes → pas d'écrasement, rotation correcte (tests Task 4).
- Archive envoyée sur le NAS → ne contient ni `.env`, ni base, ni justificatifs (vérification Task 6).
- Fichiers statiques en production (`DEBUG` faux) → servis par WhiteNoise, pas d'erreur 500 sur les gabarits (`{% static %}`) (test Task 1).

## File Structure

```text
requirements.txt                     # + gunicorn, whitenoise (modifié)
config/settings.py                   # WhiteNoise, STORAGES, STATIC_ROOT, sauvegardes, code d'installation (modifié)
config/settings_test.py              # stockage statique simple, inscription TOTP libre (modifié)
comptes/views.py                     # code d'installation avant le QR code (modifié)
templates/comptes/double_authentification.html   # (modifié)
comptes/management/commands/initialiser_compte.py
fiscalite/management/commands/sauvegarder.py
Dockerfile  .dockerignore  docker-compose.yml  .env.example  docker/entrypoint.sh
scripts/creer_archive.sh
docs/INSTALLATION-SYNOLOGY.md        # guide pas à pas
README.md                            # renvoi vers le guide (modifié)
tests/test_production.py tests/comptes/test_installation.py tests/comptes/test_initialiser_compte.py
tests/fiscalite/test_sauvegarde.py tests/test_docker.py
```

---

### Task 1: Réglages de production

**Files:**
- Modify: `requirements.txt`, `config/settings.py`, `config/settings_test.py`, `.gitignore` (ajouter `staticfiles/` et `dist/`)
- Test: `tests/test_production.py`

**Interfaces:**
- Produces: réglages `STATIC_ROOT` (`PATRIMOINE_STATIC_ROOT`, défaut `BASE_DIR / "staticfiles"`), `STORAGES` (WhiteNoise compressé avec manifeste), `SAUVEGARDES_DIR` (`DATA_DIR / "sauvegardes"`), `PATRIMOINE_CODE_INSTALLATION` (variable d'environnement, défaut vide), `PATRIMOINE_INSCRIPTION_LIBRE` (défaut `DEBUG`) ; middleware `whitenoise.middleware.WhiteNoiseMiddleware`.

- [ ] **Step 1: Écrire le test qui échoue** — `tests/test_production.py`

```python
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def test_reglages_de_production_sans_avertissement():
    donnees = tempfile.mkdtemp(prefix="patrimoine-prod-")
    env = {
        **os.environ,
        "DJANGO_DEBUG": "0",
        "DJANGO_SECRET_KEY": "une-cle-de-test-tres-longue-et-aleatoire-0123456789-abcdefghijklmnop",
        "DJANGO_ALLOWED_HOSTS": "patrimoine.exemple.fr",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://patrimoine.exemple.fr",
        "PATRIMOINE_DATA_DIR": donnees,
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    r = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=RACINE, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-c", "from django.conf import settings; import django; django.setup(); "
         "print('whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE)"],
        cwd=RACINE, env=env, capture_output=True, text=True,
    )
    assert r.stdout.strip() == "True", r.stderr
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_production.py -q`
Expected: FAIL (avertissements `security.W008`, `security.W021`… et WhiteNoise absent).

- [ ] **Step 2: Implémenter**

`requirements.txt` : ajouter les lignes `gunicorn>=23,<27` et `whitenoise>=6.9,<7`, puis `.venv/Scripts/python.exe -m pip install -q -r requirements-dev.txt`.

Dans `config/settings.py` :
- dans `MIDDLEWARE`, insérer `"whitenoise.middleware.WhiteNoiseMiddleware",` juste après `"django.middleware.security.SecurityMiddleware",` ;
- remplacer la ligne `STATIC_ROOT = DATA_DIR / "static"` par :

```python
STATIC_ROOT = Path(os.environ.get("PATRIMOINE_STATIC_ROOT", BASE_DIR / "staticfiles"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
SAUVEGARDES_DIR = DATA_DIR / "sauvegardes"
```

- après le bloc `AXES_…`, ajouter :

```python
# Enrôlement de la double authentification : en production, le QR code n'est montré qu'après saisie
# du code d'installation défini dans .env (un mot de passe volé ne suffit pas à enrôler un téléphone).
PATRIMOINE_CODE_INSTALLATION = os.environ.get("PATRIMOINE_CODE_INSTALLATION", "")
PATRIMOINE_INSCRIPTION_LIBRE = DEBUG
```

- remplacer le bloc `if not DEBUG:` final par :

```python
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # La redirection HTTPS est faite par le reverse proxy de DSM ; le conteneur n'écoute qu'en local (127.0.0.1).
    # Le préchargement HSTS engagerait tout le domaine du propriétaire : volontairement non activé.
    SILENCED_SYSTEM_CHECKS += ["security.W008", "security.W021"]
```

`config/settings_test.py` : ajouter à la fin :

```python
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PATRIMOINE_INSCRIPTION_LIBRE = True
PATRIMOINE_CODE_INSTALLATION = ""
```

Ajouter `staticfiles/` et `dist/` à `.gitignore`.

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `213 passed`, `All checks passed!`. Si `check --deploy` signale un autre avertissement, le corriger par un réglage ou le mettre en sourdine avec un commentaire, et le consigner (`Ruling:`).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(deploiement): réglages de production (WhiteNoise, HSTS, sauvegardes)"
```

---

### Task 2: Code d'installation avant l'enrôlement TOTP

**Files:**
- Modify: `comptes/views.py`, `templates/comptes/double_authentification.html`
- Test: `tests/comptes/test_installation.py`

**Interfaces:**
- Consumes: réglages `PATRIMOINE_CODE_INSTALLATION`, `PATRIMOINE_INSCRIPTION_LIBRE` (Task 1).
- Produces: la vue `comptes:double_authentification` affiche, pour un compte sans appareil confirmé et quand l'inscription n'est pas libre, un formulaire « Code d'installation » (champ `code_installation`) ; un code juste met `installation_validee` dans la session et affiche le QR code ; sans code configuré, message « enrôlement fermé ».

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/comptes/test_installation.py`

```python
import pytest

pytestmark = pytest.mark.django_db
URL = "/compte/double-authentification/"


@pytest.fixture
def production(settings):
    settings.PATRIMOINE_INSCRIPTION_LIBRE = False
    settings.PATRIMOINE_CODE_INSTALLATION = "code-secret-123"
    return settings


def test_code_d_installation_demande_avant_le_qr(client, utilisateur, production):
    client.force_login(utilisateur)
    contenu = client.get(URL).content.decode()
    assert "Code d'installation" in contenu
    assert "<svg" not in contenu


def test_mauvais_code_d_installation(client, utilisateur, production):
    client.force_login(utilisateur)
    contenu = client.post(URL, {"code_installation": "faux"}).content.decode()
    assert "Code d'installation incorrect" in contenu
    assert "<svg" not in contenu


def test_bon_code_d_installation_affiche_le_qr(client, utilisateur, production):
    client.force_login(utilisateur)
    assert client.post(URL, {"code_installation": "code-secret-123"}).status_code == 302
    assert "<svg" in client.get(URL).content.decode()


def test_enrolement_ferme_sans_code_configure(client, utilisateur, settings):
    settings.PATRIMOINE_INSCRIPTION_LIBRE = False
    settings.PATRIMOINE_CODE_INSTALLATION = ""
    client.force_login(utilisateur)
    contenu = client.get(URL).content.decode()
    assert "fermé" in contenu
    assert "<svg" not in contenu
```

Run: `.venv/Scripts/python.exe -m pytest tests/comptes/test_installation.py -q`
Expected: FAIL (le QR code s'affiche directement).

- [ ] **Step 2: Implémenter** — remplacer `comptes/views.py` par :

```python
from base64 import b32encode
from hmac import compare_digest

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

PAGE = "comptes/double_authentification.html"


def _etape_installation(request):
    """Avant d'afficher un QR code en production, exige le code d'installation du fichier .env."""
    if settings.PATRIMOINE_INSCRIPTION_LIBRE or request.session.get("installation_validee"):
        return None
    code_attendu = settings.PATRIMOINE_CODE_INSTALLATION
    if not code_attendu:
        return render(request, PAGE, {"ferme": True})
    erreur = None
    if request.method == "POST" and "code_installation" in request.POST:
        if compare_digest(request.POST["code_installation"].strip().encode(), code_attendu.encode()):
            request.session["installation_validee"] = True
            return redirect(request.get_full_path())
        erreur = "Code d'installation incorrect."
    return render(request, PAGE, {"installation": True, "erreur": erreur})


def double_authentification(request):
    if request.user.is_verified():
        return redirect("accueil")
    appareil = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    configuration = appareil is None
    if configuration:
        reponse = _etape_installation(request)
        if reponse is not None:
            return reponse
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
    return render(request, PAGE, contexte)
```

Dans `templates/comptes/double_authentification.html`, remplacer la ligne `<h1>Double authentification</h1>` par :

```html
<h1>Double authentification</h1>
{% if ferme %}
<p class="errorlist" role="alert">L'enrôlement d'un nouveau téléphone est fermé : aucun code d'installation n'est défini dans le fichier .env du serveur.</p>
{% elif installation %}
<p>Première connexion : saisissez le <strong>code d'installation</strong> que vous avez inscrit dans le fichier .env du Synology (PATRIMOINE_CODE_INSTALLATION). Le QR code s'affichera ensuite.</p>
{% if erreur %}<p class="errorlist" role="alert">{{ erreur }}</p>{% endif %}
<form method="post" class="formulaire">
  {% csrf_token %}
  <div class="champ"><label for="code_installation">Code d'installation</label><input id="code_installation" name="code_installation" type="password" autocomplete="off" required autofocus></div>
  <button class="bouton principal" type="submit">Continuer</button>
</form>
{% else %}
```

et, juste avant la ligne `<form method="post" action="{% url 'comptes:deconnexion' %}">`, insérer `{% endif %}`.

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `217 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(comptes): code d'installation avant l'enrôlement de la double authentification"
```

---

### Task 3: Création du compte au premier démarrage

**Files:**
- Create: `comptes/management/__init__.py`, `comptes/management/commands/__init__.py`, `comptes/management/commands/initialiser_compte.py`
- Test: `tests/comptes/test_initialiser_compte.py`

**Interfaces:**
- Produces: commande `manage.py initialiser_compte` : lit `PATRIMOINE_ADMIN_UTILISATEUR` et `PATRIMOINE_ADMIN_MOT_DE_PASSE` ; si l'un manque, ne fait rien ; si le compte existe, ne le modifie pas ; sinon crée un superutilisateur après validation du mot de passe (`CommandError` si trop faible).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/comptes/test_initialiser_compte.py`

```python
import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("PATRIMOINE_ADMIN_UTILISATEUR", "franck")
    monkeypatch.setenv("PATRIMOINE_ADMIN_MOT_DE_PASSE", "un-mot-de-passe-solide-2026")
    return monkeypatch


def test_cree_le_compte(env):
    call_command("initialiser_compte")
    compte = get_user_model().objects.get(username="franck")
    assert compte.is_superuser and compte.check_password("un-mot-de-passe-solide-2026")


def test_ne_modifie_pas_un_compte_existant(env):
    get_user_model().objects.create_user("franck", password="mot-de-passe-change-depuis")
    call_command("initialiser_compte")
    assert get_user_model().objects.get(username="franck").check_password("mot-de-passe-change-depuis")


def test_refuse_un_mot_de_passe_trop_court(env):
    env.setenv("PATRIMOINE_ADMIN_MOT_DE_PASSE", "court")
    with pytest.raises(CommandError, match="mot de passe"):
        call_command("initialiser_compte")
    assert not get_user_model().objects.exists()
```

Run: `.venv/Scripts/python.exe -m pytest tests/comptes/test_initialiser_compte.py -q`
Expected: FAIL — `CommandError: Unknown command: 'initialiser_compte'`.

- [ ] **Step 2: Implémenter** — fichiers `__init__.py` vides, puis `comptes/management/commands/initialiser_compte.py` :

```python
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée le compte du propriétaire au premier démarrage (variables PATRIMOINE_ADMIN_*)."

    def handle(self, *args, **options):
        identifiant = os.environ.get("PATRIMOINE_ADMIN_UTILISATEUR", "").strip()
        mot_de_passe = os.environ.get("PATRIMOINE_ADMIN_MOT_DE_PASSE", "")
        if not identifiant or not mot_de_passe:
            self.stdout.write("Aucun compte à initialiser (variables PATRIMOINE_ADMIN_* absentes).")
            return
        Utilisateur = get_user_model()
        if Utilisateur.objects.filter(username=identifiant).exists():
            self.stdout.write(f"Le compte « {identifiant} » existe déjà : il n'est pas modifié.")
            return
        try:
            validate_password(mot_de_passe, Utilisateur(username=identifiant))
        except ValidationError as erreur:
            raise CommandError("Le mot de passe du .env est refusé : " + " ".join(erreur.messages)) from None
        Utilisateur.objects.create_superuser(identifiant, password=mot_de_passe)
        self.stdout.write(self.style.SUCCESS(f"Compte « {identifiant} » créé."))
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `220 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(comptes): création du compte au premier démarrage"
```

---

### Task 4: Sauvegarde quotidienne de la base

**Files:**
- Create: `fiscalite/management/commands/sauvegarder.py`
- Test: `tests/fiscalite/test_sauvegarde.py`

**Interfaces:**
- Consumes: réglage `SAUVEGARDES_DIR` (Task 1).
- Produces: commande `manage.py sauvegarder [--garder N]` (défaut 30) : copie cohérente de la base par l'API de sauvegarde SQLite dans `SAUVEGARDES_DIR/patrimoine-AAAAMMJJ-HHMMSS-ffffff.sqlite3`, puis ne garde que les N plus récentes.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/fiscalite/test_sauvegarde.py`

```python
import sqlite3

import pytest
from django.core.management import call_command

from tests.aides import creer_bien

pytestmark = pytest.mark.django_db(transaction=True)


def test_sauvegarde_lisible(settings, tmp_path):
    settings.SAUVEGARDES_DIR = tmp_path
    creer_bien()
    call_command("sauvegarder")
    fichiers = list(tmp_path.glob("patrimoine-*.sqlite3"))
    assert len(fichiers) == 1
    with sqlite3.connect(fichiers[0]) as copie:
        assert copie.execute("select count(*) from biens_bien").fetchone()[0] == 1


def test_rotation_des_sauvegardes(settings, tmp_path):
    settings.SAUVEGARDES_DIR = tmp_path
    for i in range(32):
        (tmp_path / f"patrimoine-20200101-0000{i:02d}-000000.sqlite3").write_bytes(b"ancien")
    call_command("sauvegarder", garder=30)
    call_command("sauvegarder", garder=30)
    restants = sorted(p.name for p in tmp_path.glob("patrimoine-*.sqlite3"))
    assert len(restants) == 30
    assert sum(1 for nom in restants if not nom.startswith("patrimoine-2020")) == 2
```

Run: `.venv/Scripts/python.exe -m pytest tests/fiscalite/test_sauvegarde.py -q`
Expected: FAIL — `CommandError: Unknown command: 'sauvegarder'`.

- [ ] **Step 2: Implémenter** — `fiscalite/management/commands/sauvegarder.py`

```python
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Sauvegarde la base SQLite dans SAUVEGARDES_DIR et ne garde que les plus récentes."

    def add_arguments(self, parser):
        parser.add_argument("--garder", type=int, default=30, help="Nombre de sauvegardes conservées (30).")

    def handle(self, *args, garder, **options):
        dossier = Path(settings.SAUVEGARDES_DIR)
        dossier.mkdir(parents=True, exist_ok=True)
        cible = dossier / f"patrimoine-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3"
        connection.ensure_connection()
        with sqlite3.connect(cible) as copie:
            connection.connection.backup(copie)
        copie.close()
        sauvegardes = sorted(dossier.glob("patrimoine-*.sqlite3"), key=lambda p: p.name, reverse=True)
        for ancienne in sauvegardes[garder:]:
            ancienne.unlink()
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde créée : {cible.name} ({len(sauvegardes[:garder])} conservées)."))
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `222 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(fiscalite): sauvegarde quotidienne de la base avec rotation"
```

---

### Task 5: Image Docker et projet Container Manager

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`, `docker/entrypoint.sh`
- Test: `tests/test_docker.py`

**Interfaces:**
- Consumes: commandes `initialiser_compte` (Task 3), `sauvegarder` (Task 4) ; réglages Task 1.
- Produces: service `patrimoine` (conteneur `patrimoine`), port `127.0.0.1:8085` → 8000, volume `./data:/data`, fichier `.env` lu par `env_file`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/test_docker.py`

```python
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def lire(nom):
    return (RACINE / nom).read_text(encoding="utf-8")


def test_le_port_n_ecoute_qu_en_local_et_les_donnees_sont_persistantes():
    compose = lire("docker-compose.yml")
    assert '"127.0.0.1:8085:8000"' in compose
    assert "./data:/data" in compose
    assert "env_file: .env" in compose


def test_l_image_n_embarque_aucun_secret_ni_donnee():
    ignores = lire(".dockerignore").split()
    for motif in (".env", "data", "var", ".venv", ".git"):
        assert motif in ignores


def test_le_point_d_entree_migre_puis_lance_gunicorn_sans_root():
    entree = lire("docker/entrypoint.sh")
    assert entree.index("migrate") < entree.index("initialiser_compte") < entree.index("gunicorn")
    assert "setpriv --reuid=patrimoine" in entree
    assert "PATRIMOINE_CODE_INSTALLATION" in lire(".env.example")
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_docker.py -q`
Expected: FAIL — `FileNotFoundError: … docker-compose.yml`.

- [ ] **Step 2: Écrire les fichiers**

`Dockerfile` :

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATRIMOINE_DATA_DIR=/data \
    PATRIMOINE_STATIC_ROOT=/app/staticfiles

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput \
    && useradd --uid 1000 --create-home patrimoine \
    && mkdir -p /data \
    && chown -R patrimoine:patrimoine /data

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
```

`docker/entrypoint.sh` :

```sh
#!/bin/sh
# Prépare le dossier de données, applique les migrations, crée le compte si besoin,
# puis lance Gunicorn sous l'utilisateur non privilégié « patrimoine ».
set -e
mkdir -p /data/justificatifs /data/sauvegardes
chown -R patrimoine:patrimoine /data
lancer() { setpriv --reuid=patrimoine --regid=patrimoine --init-groups "$@"; }
lancer python manage.py migrate --noinput
lancer python manage.py initialiser_compte
exec setpriv --reuid=patrimoine --regid=patrimoine --init-groups \
    gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile -
```

`docker-compose.yml` :

```yaml
services:
  patrimoine:
    build: .
    image: patrimoine:local
    container_name: patrimoine
    restart: unless-stopped
    env_file: .env
    environment:
      PATRIMOINE_DATA_DIR: /data
    volumes:
      - ./data:/data
    ports:
      - "127.0.0.1:8085:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/compte/connexion/', timeout=5)"]
      interval: 1m
      timeout: 10s
      retries: 3
```

`.dockerignore` (un motif par ligne) :

```text
.env
data
var
.venv
.git
.superpowers
.pytest_cache
.ruff_cache
staticfiles
dist
__pycache__
```

`.env.example` :

```text
# Copiez ce fichier en « .env » à côté de docker-compose.yml sur le Synology, puis remplacez chaque valeur.
# Clé secrète : générez-la sur le PC avec  py -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET_KEY=a-remplacer
# Votre sous-domaine, plus 127.0.0.1 et localhost (contrôle de santé du conteneur)
DJANGO_ALLOWED_HOSTS=patrimoine.votredomaine.fr,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://patrimoine.votredomaine.fr
# Compte créé au premier démarrage (12 caractères minimum ; ensuite, changez-le dans l'application)
PATRIMOINE_ADMIN_UTILISATEUR=franck
PATRIMOINE_ADMIN_MOT_DE_PASSE=a-remplacer
# Code demandé avant d'afficher le QR code de la double authentification (première connexion)
PATRIMOINE_CODE_INSTALLATION=a-remplacer
```

Le fichier `.env` réel n'existe que sur le NAS ; vérifier qu'il est bien couvert par `.gitignore` (ajouter la ligne `.env` si besoin).

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `225 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(deploiement): image Docker et projet Container Manager"
```

---

### Task 6: Archive pour le NAS et guide d'installation

**Files:**
- Create: `scripts/creer_archive.sh`, `docs/INSTALLATION-SYNOLOGY.md`
- Modify: `README.md`

**Interfaces:**
- Produces: `bash scripts/creer_archive.sh` → `dist/patrimoine-<AAAAMMJJ>-<commit>.zip` (contenu du dernier commit, sans fichier ignoré) ; guide d'installation pas à pas.

- [ ] **Step 1: Script d'archive** — `scripts/creer_archive.sh`

```sh
#!/usr/bin/env bash
# Crée l'archive à copier sur le Synology (contenu du dernier commit : ni .env, ni base, ni justificatifs).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
nom="dist/patrimoine-$(date +%Y%m%d)-$(git rev-parse --short HEAD).zip"
git archive --format=zip --prefix=patrimoine/ -o "$nom" HEAD
echo "$nom"
```

- [ ] **Step 2: Guide** — `docs/INSTALLATION-SYNOLOGY.md`

```markdown
# Installer l'application sur le Synology

Durée : environ 30 minutes. Prérequis : DSM 7.2 avec **Container Manager** installé (Centre de paquets),
un nom de domaine déjà utilisé pour une autre application, et l'accès au panneau de configuration de DSM.

## 1. Préparer le sous-domaine

Chez votre fournisseur de nom de domaine, créez un enregistrement **CNAME** `patrimoine` qui pointe vers
le nom déjà utilisé par votre autre application (ou un enregistrement **A** vers la même adresse IP).
Le port 443 étant déjà ouvert sur votre box pour l'autre application, rien d'autre n'est à ouvrir.

## 2. Copier le projet sur le NAS

1. Sur le PC, l'archive `dist/patrimoine-….zip` a été préparée (sinon : `bash scripts/creer_archive.sh`).
2. Dans **File Station**, ouvrez le dossier partagé `docker` (créez-le s'il n'existe pas), créez le dossier
   `patrimoine`, puis téléversez-y l'archive.
3. Clic droit sur l'archive → **Extraire** → **Extraire ici**. Déplacez le contenu du sous-dossier `patrimoine`
   extrait directement dans `docker/patrimoine` : on doit y voir `docker-compose.yml`, `Dockerfile`, `manage.py`…

## 3. Créer le fichier .env

1. Sur le PC, générez une clé secrète : `py -c "import secrets; print(secrets.token_urlsafe(50))"`.
2. Dans File Station, copiez `.env.example` en `.env` (dans `docker/patrimoine`), ouvrez-le avec l'éditeur
   de texte de DSM (ou téléchargez-le, modifiez-le avec le Bloc-notes, renvoyez-le) et remplacez :
   - `DJANGO_SECRET_KEY` par la clé générée ;
   - `patrimoine.votredomaine.fr` (deux fois) par votre sous-domaine ;
   - `PATRIMOINE_ADMIN_MOT_DE_PASSE` par un mot de passe d'au moins 12 caractères ;
   - `PATRIMOINE_CODE_INSTALLATION` par un code de votre choix (il sera demandé à la première connexion).

## 4. Construire et démarrer le conteneur

1. Ouvrez **Container Manager** → **Projet** → **Créer**.
2. Nom du projet : `patrimoine` ; chemin : `/docker/patrimoine` ; source : **Utiliser le docker-compose.yml existant**.
3. Cliquez sur **Suivant** (pas de portail Web Station), puis **Terminé**. La construction de l'image prend
   quelques minutes ; le projet passe ensuite à l'état « En cours d'exécution ».
4. Dans **Conteneur** → `patrimoine` → **Journal**, vous devez lire « Compte « franck » créé » puis les
   lignes de démarrage de Gunicorn.

## 5. Publier l'application en HTTPS (proxy inversé)

1. **Panneau de configuration** → **Portail de connexion** → **Avancé** → **Proxy inversé** → **Créer**.
2. Nom : `patrimoine`. Source : protocole **HTTPS**, nom d'hôte `patrimoine.votredomaine.fr`, port **443**,
   cochez **Activer HSTS**. Destination : protocole **HTTP**, nom d'hôte **localhost**, port **8085**.
3. Onglet **En-tête personnalisé** → **Créer** → **En-tête personnalisé** : nom `X-Forwarded-Proto`, valeur `https`.
4. **Enregistrer**.

## 6. Certificat HTTPS

1. **Panneau de configuration** → **Sécurité** → **Certificat** → **Ajouter** → **Ajouter un nouveau certificat**
   → **Obtenir un certificat auprès de Let's Encrypt** → nom de domaine `patrimoine.votredomaine.fr`.
   (Si votre certificat existant couvre déjà `*.votredomaine.fr`, cette étape est inutile.)
2. Bouton **Paramètres** (même écran) : pour le service `patrimoine` (proxy inversé), choisissez ce certificat.

## 7. Première connexion

1. Ouvrez `https://patrimoine.votredomaine.fr` : connectez-vous avec l'identifiant et le mot de passe du `.env`.
2. Saisissez le **code d'installation**, scannez le QR code avec votre application d'authentification,
   puis saisissez le code à 6 chiffres.
3. Changez votre mot de passe : **Paramètres** → **Utilisateurs** → votre compte → « formulaire » de mot de passe.
4. Par sécurité, effacez ensuite la valeur de `PATRIMOINE_CODE_INSTALLATION` dans `.env` puis, dans
   Container Manager, **Projet** → `patrimoine` → **Arrêter**, puis **Démarrer** (l'enrôlement d'un nouveau
   téléphone sera alors fermé ; remettez un code le jour où vous changez de téléphone).

## 8. Sauvegardes

1. **Panneau de configuration** → **Planificateur de tâches** → **Créer** → **Tâche planifiée** → **Script défini
   par l'utilisateur**. Utilisateur : `root`. Planification : tous les jours à 3 h. Script :
   `docker exec -u patrimoine patrimoine python manage.py sauvegarder`
2. **Hyper Backup** : créez une tâche qui sauvegarde le dossier `docker/patrimoine` (base, justificatifs,
   sauvegardes et `.env`) vers un disque externe ou un service cloud, avec **chiffrement côté client**.

## Mettre à jour l'application

1. Sur le PC : `bash scripts/creer_archive.sh`.
2. Sur le NAS : extrayez la nouvelle archive dans `docker/patrimoine` en remplaçant les fichiers
   (le dossier `data` et le fichier `.env` ne sont pas dans l'archive et restent intacts).
3. Container Manager → **Projet** → `patrimoine` → **Arrêter**, puis **Action** → **Construire** (Build) et **Démarrer**.
   Les migrations de la base s'appliquent automatiquement au démarrage.

## Recommandé

Pare-feu de DSM (**Panneau de configuration** → **Sécurité** → **Pare-feu**) : n'autoriser le port 443 que
depuis la France ; activer le **blocage automatique** des adresses IP (**Sécurité** → **Protection**).
```

Dans `README.md`, ajouter à la fin :

```markdown
## Installer sur le Synology

Suivre [docs/INSTALLATION-SYNOLOGY.md](docs/INSTALLATION-SYNOLOGY.md). Archive à copier sur le NAS :
`bash scripts/creer_archive.sh` (dans `dist/`).
```

- [ ] **Step 3: Vérifier**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix . && git add -A && git commit -q -m "docs: guide d'installation Synology et archive" && bash scripts/creer_archive.sh && .venv/Scripts/python.exe -c "import zipfile,glob; n=zipfile.ZipFile(sorted(glob.glob('dist/*.zip'))[-1]).namelist(); print(len(n), any(x.endswith('/.env') for x in n), any('/var/' in x or '/data/' in x for x in n), 'patrimoine/Dockerfile' in n)"`
Expected: `225 passed`, `All checks passed!`, chemin de l'archive, puis `<nombre> False False True`.

- [ ] **Step 4: Commit** (fait à l'étape 3 ; ajouter le message complet avec les lignes d'attribution).
