from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from operations.models import Categorie, Operation
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def donnees(bien, **kw):
    d = {
        "bien": bien.pk, "date_paiement": "2025-07-01", "categorie": Categorie.objects.get(code="travaux").pk,
        "libelle": "Remplacement du chauffe-eau", "montant": "1 180", "commentaire": "",
    }
    d.update(kw)
    return d


def test_creation_avec_justificatif(client_verifie):
    b = creer_bien()
    fichier = SimpleUploadedFile("facture.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    r = client_verifie.post(reverse("operations:creer"), donnees(b, justificatif=fichier))
    assert r.status_code == 302
    op = Operation.objects.get()
    assert op.montant == 118_000
    assert op.justificatif.name.endswith(".pdf")


def test_justificatif_au_mauvais_format_refuse(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("operations:creer"), donnees(b, justificatif=SimpleUploadedFile("x.exe", b"MZ")))
    assert r.status_code == 200
    assert "Formats acceptés" in r.content.decode()
    assert not Operation.objects.exists()


def test_filtre_par_nature(client_verifie):
    b = creer_bien()
    creer_operation(b, "loyer", 62_000, date(2025, 9, 5), "Loyer septembre")
    creer_operation(b, "teom", 16_800, date(2025, 10, 15), "Ordures ménagères")
    contenu = client_verifie.get(reverse("operations:liste") + "?annee=2025&nature=non-deductibles").content.decode()
    assert "Ordures ménagères" in contenu
    assert "Loyer septembre" not in contenu


def test_annee_par_defaut_la_plus_recente(client_verifie):
    b = creer_bien()
    creer_operation(b, "loyer", 62_000, date(2024, 9, 5), "Loyer 2024")
    creer_operation(b, "loyer", 62_000, date(2025, 9, 5), "Loyer 2025")
    contenu = client_verifie.get(reverse("operations:liste")).content.decode()
    assert "Loyer 2025" in contenu
    assert "Loyer 2024" not in contenu


def test_justificatif_protege(client_verifie):
    b = creer_bien()
    op = creer_operation(
        b, "travaux", 1000, date(2025, 1, 2), justificatif=SimpleUploadedFile("f.pdf", b"%PDF contenu")
    )
    url = reverse("operations:justificatif", args=[op.pk])
    assert Client().get(url).status_code == 302
    r = client_verifie.get(url)
    assert r.status_code == 200
    assert b"".join(r.streaming_content) == b"%PDF contenu"


def test_suppression_uniquement_en_post(client_verifie):
    op = creer_operation(creer_bien(), "loyer", 62_000, date(2025, 1, 5))
    url = reverse("operations:supprimer", args=[op.pk])
    assert client_verifie.get(url).status_code == 405
    assert client_verifie.post(url).status_code == 302
    assert not Operation.objects.exists()
