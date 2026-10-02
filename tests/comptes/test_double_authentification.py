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
