import pytest
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user("proprietaire", password="mot-de-passe-solide-123")


@pytest.fixture
def client_verifie(client, utilisateur):
    appareil = TOTPDevice.objects.create(user=utilisateur, name="test", confirmed=True)
    client.force_login(utilisateur)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = appareil.persistent_id
    session.save()
    return client
