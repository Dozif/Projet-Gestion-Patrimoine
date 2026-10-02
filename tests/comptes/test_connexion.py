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
