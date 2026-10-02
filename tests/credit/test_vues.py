import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from credit.models import Echeance, Pret
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db
CSV_FR = "Date;Capital amorti;Intérêts;Assurance\n05/01/2025;612,45;173,20;18,00\n05/02/2025;613,10;172,55;18,00\n"
MAPPING = {"date": "Date", "capital": "Capital amorti", "interets": "Intérêts", "assurance": "Assurance"}


def creer_pret():
    return Pret.objects.create(bien=creer_bien(), banque="Banque", capital_emprunte=15_000_000, date_debut="2015-01-05")


def test_creation_d_un_pret(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("credit:creer"), {
        "bien": b.pk, "banque": "Banque", "libelle": "", "capital_emprunte": "150 000", "date_debut": "2015-01-05",
    })
    assert r.status_code == 302
    assert Pret.objects.get().capital_emprunte == 15_000_000


def test_import_en_trois_etapes_sans_doublon(client_verifie):
    pret = creer_pret()
    url = reverse("credit:importer", args=[pret.pk])
    fichier = SimpleUploadedFile("echeancier.csv", CSV_FR.encode("cp1252"))
    assert client_verifie.post(url, {"fichier": fichier}).status_code == 302
    assert "Colonne de la date" in client_verifie.get(url).content.decode()
    apercu = client_verifie.post(url, {**MAPPING, "apercu": "1"})
    assert "2 échéances" in apercu.content.decode()
    assert client_verifie.post(url, {**MAPPING, "importer": "1"}).status_code == 302
    assert Echeance.objects.filter(pret=pret).count() == 2
    client_verifie.post(url, {"fichier": SimpleUploadedFile("e.csv", CSV_FR.encode("utf-8"))})
    client_verifie.post(url, {**MAPPING, "importer": "1"})
    assert Echeance.objects.filter(pret=pret).count() == 2


def test_detail_affiche_les_totaux_annuels(client_verifie):
    pret = creer_pret()
    Echeance.objects.create(pret=pret, date="2025-01-05", capital=61_245, interets=17_320, assurance=1_800)
    Echeance.objects.create(pret=pret, date="2025-02-05", capital=61_310, interets=17_255, assurance=1_800)
    contenu = client_verifie.get(reverse("credit:detail", args=[pret.pk])).content.decode()
    assert "381,75 €" in contenu


def test_fichier_illisible_sans_erreur_serveur(client_verifie):
    pret = creer_pret()
    url = reverse("credit:importer", args=[pret.pk])
    r = client_verifie.post(url, {"fichier": SimpleUploadedFile("e.csv", b"Date;\x81\x8d")})
    assert r.status_code == 302
    assert "Encodage" in client_verifie.get(url).content.decode()
