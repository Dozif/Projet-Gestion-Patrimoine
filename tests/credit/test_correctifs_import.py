import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from credit.import_csv import Colonnes, ErreurImport, lire_echeancier, lire_entetes

from .test_vues import CSV_FR, creer_pret

pytestmark = pytest.mark.django_db
CELLULE_GEANTE = "Date;Capital;Intérêts\n05/01/2025;" + '"' + "1" * 200_000 + '"' + ";1\n"


def test_cellule_geante_signalee_comme_erreur_d_import():
    with pytest.raises(ErreurImport):
        lire_echeancier(CELLULE_GEANTE, Colonnes("Date", "Capital", "Intérêts"))


def test_entete_geante_signalee_comme_erreur_d_import():
    with pytest.raises(ErreurImport):
        lire_entetes('"' + "x" * 200_000 + '";Date\n')


def test_recommencer_n_efface_plus_l_import_en_get(client_verifie):
    pret = creer_pret()
    url = reverse("credit:importer", args=[pret.pk])
    client_verifie.post(url, {"fichier": SimpleUploadedFile("e.csv", CSV_FR.encode("utf-8"))})
    client_verifie.get(url + "?recommencer=1")
    assert f"import_echeancier_{pret.pk}" in client_verifie.session


def test_recommencer_en_post_efface_l_import(client_verifie):
    pret = creer_pret()
    url = reverse("credit:importer", args=[pret.pk])
    client_verifie.post(url, {"fichier": SimpleUploadedFile("e.csv", CSV_FR.encode("utf-8"))})
    assert client_verifie.post(url, {"recommencer": "1"}).status_code == 302
    assert f"import_echeancier_{pret.pk}" not in client_verifie.session
