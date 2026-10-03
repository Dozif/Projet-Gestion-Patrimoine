from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from .test_double_authentification import code_pour

pytestmark = pytest.mark.django_db
URL = "/compte/double-authentification/"


@pytest.fixture
def appareil(utilisateur):
    return TOTPDevice.objects.create(user=utilisateur, name="tel", confirmed=True)


@pytest.fixture
def production(settings):
    settings.PATRIMOINE_INSCRIPTION_LIBRE = False
    settings.PATRIMOINE_CODE_INSTALLATION = "code-secret-123456"
    return settings


def bloquer(appareil, echecs, il_y_a):
    appareil.throttling_failure_count = echecs
    appareil.throttling_failure_timestamp = timezone.now() - il_y_a
    appareil.save()


def test_le_delai_de_la_double_authentification_est_plafonne(client, utilisateur, appareil):
    # Sans plafond, 20 échecs imposeraient 2**19 s (6 jours) : le propriétaire serait refusé.
    bloquer(appareil, 20, timedelta(seconds=600))
    client.force_login(utilisateur)
    r = client.post(URL, {"code": code_pour(appareil)})
    assert r.status_code == 302
    appareil.refresh_from_db()
    assert appareil.throttling_failure_count == 0


def test_le_blocage_est_annonce_comme_tel(client, utilisateur, appareil):
    bloquer(appareil, 5, timedelta(seconds=1))
    client.force_login(utilisateur)
    contenu = client.post(URL, {"code": code_pour(appareil)}).content.decode()
    assert "Trop de codes incorrects" in contenu
    assert "heure de votre téléphone" not in contenu


def test_un_nouvel_enrolement_genere_une_cle_neuve(client, utilisateur, production):
    ancien = TOTPDevice.objects.create(user=utilisateur, name="abandonné", confirmed=False)
    client.force_login(utilisateur)
    client.post(URL, {"code_installation": "code-secret-123456"})
    client.get(URL)
    appareils = TOTPDevice.objects.filter(user=utilisateur)
    assert appareils.count() == 1
    assert appareils.get().key != ancien.key


def test_la_validation_du_code_d_installation_ne_survit_pas_a_l_enrolement(client, utilisateur, production):
    client.force_login(utilisateur)
    client.post(URL, {"code_installation": "code-secret-123456"})
    client.get(URL)
    nouveau = TOTPDevice.objects.get(user=utilisateur)
    client.post(URL, {"code": code_pour(nouveau)})
    assert "installation_validee" not in client.session


def test_la_session_change_d_identifiant_apres_la_double_authentification(client, utilisateur, appareil):
    client.force_login(utilisateur)
    avant = client.session.session_key
    client.post(URL, {"code": code_pour(appareil)})
    assert client.session.session_key != avant


def test_l_admin_masque_les_secrets_otp():
    assert settings.OTP_ADMIN_HIDE_SENSITIVE_DATA is True
