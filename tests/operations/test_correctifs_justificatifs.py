from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from operations.models import valider_justificatif
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def avec_justificatif(contenu=b"%PDF-1.4 facture"):
    return creer_operation(
        creer_bien(), "travaux", 1000, date(2025, 1, 2), justificatif=SimpleUploadedFile("f.pdf", contenu)
    )


@pytest.mark.parametrize("nom,contenu", [
    ("page.pdf", b"<html><script>alert(1)</script>"),
    ("photo.png", b"<svg onload=alert(1)>"),
    ("photo.jpg", b"%PDF-1.4 pas une image"),
])
def test_contenu_qui_ne_correspond_pas_a_l_extension_refuse(nom, contenu):
    with pytest.raises(ValidationError):
        valider_justificatif(SimpleUploadedFile(nom, contenu))


@pytest.mark.parametrize("nom,contenu", [
    ("f.pdf", b"%PDF-1.7 ..."),
    ("f.png", b"\x89PNG\r\n\x1a\n..."),
    ("f.jpeg", b"\xff\xd8\xff\xe0..."),
])
def test_vrais_formats_acceptes(nom, contenu):
    valider_justificatif(SimpleUploadedFile(nom, contenu))


def test_justificatif_servi_en_piece_jointe(client_verifie):
    op = avec_justificatif()
    r = client_verifie.get(reverse("operations:justificatif", args=[op.pk]))
    assert r["Content-Disposition"].startswith("attachment")


def test_suppression_de_l_operation_efface_le_fichier(client_verifie):
    op = avec_justificatif()
    chemin = op.justificatif.path
    client_verifie.post(reverse("operations:supprimer", args=[op.pk]))
    assert not op.justificatif.storage.exists(op.justificatif.name), chemin


def test_remplacement_du_justificatif_efface_l_ancien(client_verifie):
    op = avec_justificatif()
    ancien = op.justificatif.name
    donnees = {
        "bien": op.bien_id, "date_paiement": "2025-01-02", "categorie": op.categorie_id,
        "libelle": op.libelle, "montant": "10", "commentaire": "",
        "justificatif": SimpleUploadedFile("g.pdf", b"%PDF-1.4 nouvelle"),
    }
    assert client_verifie.post(reverse("operations:modifier", args=[op.pk]), donnees).status_code == 302
    assert not op.justificatif.storage.exists(ancien)


def test_modification_sans_nouveau_fichier_conserve_le_justificatif(client_verifie):
    op = avec_justificatif()
    ancien = op.justificatif.name
    donnees = {
        "bien": op.bien_id, "date_paiement": "2025-01-02", "categorie": op.categorie_id,
        "libelle": "Nouveau libellé", "montant": "10", "commentaire": "",
    }
    assert client_verifie.post(reverse("operations:modifier", args=[op.pk]), donnees).status_code == 302
    op.refresh_from_db()
    assert op.justificatif.name == ancien
    assert op.justificatif.storage.exists(ancien)
