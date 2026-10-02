from datetime import date

import pytest
from django.core.management import call_command
from django.urls import reverse

from biens.models import Bien
from declaration.models import DeclarationFigee
from tests.aides import creer_operation

pytestmark = pytest.mark.django_db
PAGE = "/declaration/?annee=2025"


@pytest.fixture
def demo():
    call_command("seed_demo")


def test_figer_la_declaration(client_verifie, demo):
    r = client_verifie.post(reverse("declaration:figer", args=[2025]))
    assert r.status_code == 302
    assert DeclarationFigee.objects.get(annee=2025).donnees["cases"]["4BC"] == 90_600
    contenu = client_verifie.get(PAGE).content.decode()
    assert "Figée le" in contenu
    assert "ont changé" not in contenu
    assert "window.print()" in contenu


def test_figer_uniquement_en_post(client_verifie, demo):
    assert client_verifie.get(reverse("declaration:figer", args=[2025])).status_code == 405


def test_modification_apres_gel_signalee(client_verifie, demo):
    client_verifie.post(reverse("declaration:figer", args=[2025]))
    creer_operation(Bien.objects.get(nom="T3 Centre"), "travaux", 10_000, date(2025, 11, 2), "Peinture")
    assert "ont changé" in client_verifie.get(PAGE).content.decode()


def test_defiger(client_verifie, demo):
    client_verifie.post(reverse("declaration:figer", args=[2025]))
    client_verifie.post(reverse("declaration:defiger", args=[2025]))
    assert not DeclarationFigee.objects.exists()
