import pytest
from django.core.management import call_command
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

pytestmark = pytest.mark.django_db


@pytest.fixture
def appareil_bloque(utilisateur):
    return TOTPDevice.objects.create(
        user=utilisateur, name="tel", confirmed=True,
        throttling_failure_count=12, throttling_failure_timestamp=timezone.now(),
    )


def test_remet_le_delai_a_zero(appareil_bloque):
    call_command("debloquer_2fa")
    appareil_bloque.refresh_from_db()
    assert appareil_bloque.throttling_failure_count == 0
    assert appareil_bloque.throttling_failure_timestamp is None


def test_telephone_perdu_supprime_l_appareil(appareil_bloque):
    call_command("debloquer_2fa", "--supprimer-appareil")
    assert not TOTPDevice.objects.exists()
