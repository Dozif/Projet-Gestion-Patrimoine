from datetime import date

import pytest

from credit.import_csv import Colonnes, EcheanceLue, ErreurImport, decoder, lire_echeancier, lire_entetes

CSV_FR = "Date;Capital amorti;Intérêts;Assurance\n05/01/2025;612,45;173,20;18,00\n05/02/2025;613,10;172,55;18,00\n\n"
COLONNES_FR = Colonnes("Date", "Capital amorti", "Intérêts", "Assurance")


def test_format_francais():
    lues = lire_echeancier(CSV_FR, COLONNES_FR)
    assert len(lues) == 2
    assert lues[0] == EcheanceLue(date(2025, 1, 5), 61_245, 17_320, 1_800)


def test_virgule_et_point_decimal_sans_assurance():
    lues = lire_echeancier("date,capital,interets\n2025-01-05,612.45,173.20\n", Colonnes("date", "capital", "interets"))
    assert lues == [EcheanceLue(date(2025, 1, 5), 61_245, 17_320, 0)]


def test_colonne_introuvable():
    with pytest.raises(ErreurImport, match="Colonnes introuvables"):
        lire_echeancier(CSV_FR, Colonnes("Date", "Capital", "Intérêts"))


def test_ligne_invalide_indique_son_numero():
    with pytest.raises(ErreurImport, match="Ligne 3"):
        lire_echeancier("Date;Capital;Intérêts\n05/01/2025;1;1\nxx;1;1\n", Colonnes("Date", "Capital", "Intérêts"))


def test_decodage_cp1252_et_bom():
    assert decoder("Intérêts".encode("cp1252")) == "Intérêts"
    assert decoder("﻿Date".encode()) == "Date"


def test_entetes():
    assert lire_entetes(CSV_FR) == ["Date", "Capital amorti", "Intérêts", "Assurance"]


def test_fichier_sans_echeance():
    with pytest.raises(ErreurImport, match="Aucune échéance"):
        lire_echeancier("Date;Capital;Intérêts\n", Colonnes("Date", "Capital", "Intérêts"))
