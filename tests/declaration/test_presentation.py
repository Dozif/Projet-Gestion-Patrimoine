from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from declaration.presentation import (
    cases_2042,
    colonnes_biens,
    detail_ligne,
    empreinte,
    estimation_impot,
    lignes_declaration,
    resultat_vers_dict,
)
from fiscalite.services import calculer_annee
from operations.models import Categorie, Operation

pytestmark = pytest.mark.django_db


@pytest.fixture
def calcul_2025():
    call_command("seed_demo")
    return calculer_annee(2025)


def test_lignes_de_la_declaration(calcul_2025):
    resultat, _ = calcul_2025
    lignes = {ligne["code"]: ligne for ligne in lignes_declaration(resultat)}
    assert lignes["211"]["valeurs"] == [744_000, 936_000]
    assert lignes["211"]["total"] == 1_680_000
    assert lignes["230"]["valeurs"] == [-21_000, -29_000]
    assert lignes["240"]["type"] == "total"
    assert "212" not in lignes
    assert lignes[""]["valeurs"] == [300_900, -391_500]
    assert lignes[""]["type"] == "resultat"


def test_colonnes_dans_l_ordre_des_biens(calcul_2025):
    assert colonnes_biens(*calcul_2025) == ["T2 Les Tilleuls", "T3 Centre"]


def test_detail_des_travaux(calcul_2025):
    detail = detail_ligne(*calcul_2025, "224")
    assert detail["total"] == 640_000
    assert "agrandissement" in detail["regle"]
    assert sorted(o["montant"] for o in detail["operations"]) == [220_000, 420_000]
    assert any("Rénovation de la salle d'eau" in o["texte"] for o in detail["operations"])


def test_detail_des_interets_par_echeance(calcul_2025):
    assert len(detail_ligne(*calcul_2025, "250")["operations"]) == 24


def test_detail_d_une_ligne_inconnue(calcul_2025):
    assert detail_ligne(*calcul_2025, "999") is None


@pytest.mark.parametrize(
    "revenu,deficit,attendu",
    [(100_000, 0, {"impot": 47_200, "economie": 0}), (0, 90_600, {"impot": 0, "economie": 27_180})],
)
def test_estimation_impot(revenu, deficit, attendu):
    assert estimation_impot(revenu, deficit, Decimal("30"), Decimal("17.2")) == attendu


def test_cases_2042(calcul_2025):
    resultat, _ = calcul_2025
    assert [(c["code"], c["montant"]) for c in cases_2042(resultat)] == [
        ("4BA", 0), ("4BB", 0), ("4BC", 90_600), ("4BD", 355_000)
    ]


def test_serialisation_et_empreinte_stable(calcul_2025):
    donnees = resultat_vers_dict(*calcul_2025)
    assert donnees["cases"]["4BC"] == 90_600
    assert len(donnees["biens"]) == 2
    assert empreinte(donnees) == empreinte(resultat_vers_dict(*calculer_annee(2025)))


def test_empreinte_change_si_les_donnees_changent(calcul_2025):
    avant = empreinte(resultat_vers_dict(*calcul_2025))
    t3 = calcul_2025[1].biens[1]
    Operation.objects.create(
        bien_id=t3.id, categorie=Categorie.objects.get(code="travaux"), date_paiement=date(2025, 11, 2),
        montant=10_000, libelle="Peinture",
    )
    assert empreinte(resultat_vers_dict(*calculer_annee(2025))) != avant


def test_colonnes_justes_avec_les_arrondis(calcul_2025):
    for bien in calcul_2025[1].biens:
        Operation.objects.create(
            bien_id=bien.id, categorie=Categorie.objects.get(code="travaux"), date_paiement=date(2025, 11, 2),
            montant=49, libelle="Petite fourniture",
        )
    resultat, _ = calculer_annee(2025)
    lignes = {ligne["code"]: ligne for ligne in lignes_declaration(resultat)}
    assert lignes["224"]["valeurs"] == [0, 640_000]
    assert lignes["224"]["total"] == 640_000
    assert lignes["240"]["valeurs"] == [225_100, 932_500]
    assert lignes[""]["valeurs"] == [300_900, -391_500]
    assert lignes[""]["total"] == -90_600


def test_bien_sans_activite_ignore(calcul_2025):
    from biens.models import Bien
    avant = empreinte(resultat_vers_dict(*calcul_2025))
    Bien.objects.create(nom="Studio acheté en 2026", surface_habitable=Decimal("20"))
    Bien.objects.filter(nom="T3 Centre").update(nom="T3 Centre-ville")
    resultat, contexte = calculer_annee(2025)
    assert colonnes_biens(resultat, contexte) == ["T2 Les Tilleuls", "T3 Centre-ville"]
    assert empreinte(resultat_vers_dict(resultat, contexte)) == avant
