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
