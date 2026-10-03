import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db
CONNEXION = "/compte/connexion/"


def test_corps_volumineux_refuse_avant_authentification(client):
    r = client.post(CONNEXION, {"username": "x", "password": "y"}, CONTENT_LENGTH=str(70 * 1024))
    assert r.status_code == 413


def test_connexion_normale_non_bloquee(client):
    r = client.post(CONNEXION, {"username": "x", "password": "y"})
    assert r.status_code != 413


def test_session_non_verifiee_limitee_comme_un_anonyme(client, utilisateur):
    client.force_login(utilisateur)
    r = client.post("/compte/double-authentification/", {"code": "1"}, CONTENT_LENGTH=str(70 * 1024))
    assert r.status_code == 413


def test_corps_au_dela_du_plafond_anonyme_accepte_une_fois_verifie(client_verifie):
    r = client_verifie.post("/operations/nouvelle/", {"commentaire": "x" * 100 * 1024})
    assert r.status_code != 413


def test_plafond_global_meme_verifie(client_verifie):
    r = client_verifie.post("/operations/nouvelle/", {}, CONTENT_LENGTH=str(13 * 1024 * 1024))
    assert r.status_code == 413


def test_un_seul_fichier_par_requete():
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES == 1
