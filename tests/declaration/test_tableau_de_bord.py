import pytest
from django.core.management import call_command

from fiscalite.models import ParametresAnnuels

pytestmark = pytest.mark.django_db


def test_tableau_de_bord_2025(client_verifie):
    call_command("seed_demo")
    contenu = client_verifie.get("/?annee=2025").content.decode()
    assert "T2 Les Tilleuls" in contenu
    assert "7 440 €" in contenu
    assert "−906 €" in contenu
    assert "271,80 €" in contenu


def test_tableau_de_bord_sans_donnees(client_verifie):
    r = client_verifie.get("/")
    assert r.status_code == 200
    assert "Tableau de bord" in r.content.decode()


def test_parametres_manquants(client_verifie):
    ParametresAnnuels.objects.filter(annee=2025).delete()
    r = client_verifie.get("/?annee=2025")
    assert r.status_code == 200
    assert "Paramètres fiscaux 2025 absents" in r.content.decode()


def test_annee_anterieure_a_la_premiere_annee_geree(client_verifie):
    r = client_verifie.get("/?annee=2020")
    assert r.status_code == 200
    assert "première année" in r.content.decode()
