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


def test_ne_recree_pas_de_compte_si_un_utilisateur_existe(env):
    get_user_model().objects.create_user("autre-nom", password="mot-de-passe-change-depuis")
    call_command("initialiser_compte")
    assert not get_user_model().objects.filter(username="franck").exists()
