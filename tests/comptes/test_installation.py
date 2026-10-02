import pytest

pytestmark = pytest.mark.django_db
URL = "/compte/double-authentification/"


@pytest.fixture
def production(settings):
    settings.PATRIMOINE_INSCRIPTION_LIBRE = False
    settings.PATRIMOINE_CODE_INSTALLATION = "code-secret-123456"
    return settings


def test_code_d_installation_demande_avant_le_qr(client, utilisateur, production):
    client.force_login(utilisateur)
    contenu = client.get(URL).content.decode()
    assert "Code d&#x27;installation" in contenu or "Code d'installation" in contenu
    assert "<svg" not in contenu


def test_mauvais_code_d_installation(client, utilisateur, production):
    client.force_login(utilisateur)
    contenu = client.post(URL, {"code_installation": "faux"}).content.decode()
    assert "Code d&#x27;installation incorrect" in contenu or "Code d'installation incorrect" in contenu
    assert "<svg" not in contenu


def test_bon_code_d_installation_affiche_le_qr(client, utilisateur, production):
    client.force_login(utilisateur)
    assert client.post(URL, {"code_installation": "code-secret-123456"}).status_code == 302
    assert "<svg" in client.get(URL).content.decode()


def test_enrolement_ferme_sans_code_configure(client, utilisateur, settings):
    settings.PATRIMOINE_INSCRIPTION_LIBRE = False
    settings.PATRIMOINE_CODE_INSTALLATION = ""
    client.force_login(utilisateur)
    contenu = client.get(URL).content.decode()
    assert "fermé" in contenu
    assert "<svg" not in contenu


def test_code_d_installation_trop_court_ferme_l_enrolement(client, utilisateur, settings):
    settings.PATRIMOINE_INSCRIPTION_LIBRE = False
    settings.PATRIMOINE_CODE_INSTALLATION = "a-remplacer"
    client.force_login(utilisateur)
    contenu = client.get(URL).content.decode()
    assert "fermé" in contenu
    assert "<svg" not in contenu


def test_trop_d_essais_du_code_deconnecte(client, utilisateur, production):
    client.force_login(utilisateur)
    for _ in range(4):
        client.post(URL, {"code_installation": "faux"})
    r = client.post(URL, {"code_installation": "faux"})
    assert r.status_code == 302
    assert "/compte/connexion/" in r.url
    assert "_auth_user_id" not in client.session
