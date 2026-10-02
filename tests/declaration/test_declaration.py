import pytest
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db
URL = "/declaration/"


@pytest.fixture
def demo():
    call_command("seed_demo")


def test_declaration_2025(client_verifie, demo):
    contenu = client_verifie.get(URL + "?annee=2025").content.decode()
    assert "Déclaration 2025" in contenu
    assert "T3 Centre" in contenu
    assert "Case 4BC" in contenu
    assert "906 €" in contenu
    assert reverse("declaration:export_csv", args=[2025]) in contenu
    assert ">Déclaration</a>" in contenu


def test_detail_d_une_ligne(client_verifie, demo):
    contenu = client_verifie.get(URL + "?annee=2025&ligne=224").content.decode()
    assert "Rénovation de la salle d" in contenu
    assert "agrandissement" in contenu


def test_ligne_inconnue_ignoree(client_verifie, demo):
    r = client_verifie.get(URL + "?annee=2025&ligne=abc")
    assert r.status_code == 200
    assert 'id="detail"' not in r.content.decode()


def test_annee_par_defaut(client_verifie):
    assert client_verifie.get(URL).status_code == 200


def test_reduction_pinel_de_l_annee(client_verifie, demo):
    assert "1 680 €" in client_verifie.get(URL + "?annee=2025").content.decode()
