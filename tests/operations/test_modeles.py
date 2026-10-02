from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

import fiscal
from operations.models import Categorie, ReleveAgence, valider_justificatif
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def test_categories_initiales_presentes():
    travaux = Categorie.objects.get(code="travaux")
    assert (travaux.nature, travaux.ligne_2044) == ("CHARGE_DEDUCTIBLE", "224")
    assert Categorie.objects.get(code="teom").nature == "CHARGE_NON_DEDUCTIBLE"
    assert Categorie.objects.count() == 19


def test_toutes_les_categories_initiales_sont_coherentes():
    for categorie in Categorie.objects.all():
        categorie.full_clean()


def test_categorie_incoherente_refusee():
    with pytest.raises(ValidationError):
        Categorie(code="x", libelle="X", nature="CHARGE_DEDUCTIBLE", ligne_2044="211").full_clean()


def test_operation_vers_fiscal():
    o = creer_operation(creer_bien(), "travaux", 420_000, date(2025, 3, 12))
    assert o.vers_fiscal() == fiscal.Operation(
        id=o.pk, bien_id=o.bien_id, date_paiement=date(2025, 3, 12), montant=420_000,
        nature=fiscal.Nature.CHARGE_DEDUCTIBLE, ligne_2044="224", libelle="travaux",
    )


def test_operation_non_deductible_sans_ligne():
    o = creer_operation(creer_bien(), "teom", 16_800, date(2025, 10, 15))
    assert o.vers_fiscal().ligne_2044 is None


def test_justificatif_extension_refusee():
    with pytest.raises(ValidationError, match="Formats acceptés"):
        valider_justificatif(SimpleUploadedFile("virus.exe", b"MZ"))


def test_justificatif_trop_lourd_refuse():
    with pytest.raises(ValidationError, match="10 Mo"):
        valider_justificatif(SimpleUploadedFile("gros.pdf", b"0" * (10 * 1024 * 1024 + 1)))


def test_releve_net_verse():
    releve = ReleveAgence(loyer_brut=62_000, charges_recues=4_000, honoraires=4_340)
    assert releve.net_verse == 61_660
