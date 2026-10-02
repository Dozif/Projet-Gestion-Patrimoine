from fiscal.calcul_2044 import calculer_bien
from fiscal.modeles import Bien, Nature, ParametresAnnuels
from tests.fiscal.fabrique import op

B = Bien(id=1, nom="T2")
P = ParametresAnnuels(annee=2025)


def test_recettes_et_total_215():
    r = calculer_bien(2025, B, [op(1, "211", 62000), op(1, "211", 62000), op(1, "214", 10000)], P)
    assert r.lignes["211"].montant == 124000
    assert r.lignes["214"].montant == 10000
    assert r.lignes["215"].montant == 134000
    assert r.recettes == 134000


def test_frais_avec_forfait_et_regularisation():
    ops = [
        op(1, "211", 744000), op(1, "221", 52100), op(1, "223", 14800),
        op(1, "227", 81200), op(1, "229", 96000), op(1, "230", 21000),
    ]
    r = calculer_bien(2025, B, ops, P)
    assert r.lignes["222"].montant == 2000
    assert r.lignes["230"].montant == 21000
    assert r.frais == 52100 + 2000 + 14800 + 81200 + 96000 - 21000


def test_interets_et_resultat():
    ops = [
        op(1, "211", 744000), op(1, "221", 52100), op(1, "223", 14800),
        op(1, "227", 81200), op(1, "229", 96000), op(1, "230", 21000), op(1, "250", 218000),
    ]
    r = calculer_bien(2025, B, ops, P)
    assert r.interets == 218000
    assert r.resultat == 300900


def test_explication_liste_les_operations():
    travaux = op(1, "224", 420000)
    r = calculer_bien(2025, B, [op(1, "211", 1000), travaux], P)
    assert r.lignes["224"].explication.operation_ids == (travaux.id,)
    assert "agrandissement" in r.lignes["224"].explication.regle


def test_ignore_autres_annees_autres_biens_et_operations_hors_2044():
    ops = [
        op(1, "211", 62000),
        op(1, "211", 62000, annee=2024),
        op(2, "211", 99900),
        op(1, None, 14000, nature=Nature.RECETTE_NON_IMPOSABLE),
        op(1, None, 61245, nature=Nature.CHARGE_NON_DEDUCTIBLE),
    ]
    r = calculer_bien(2025, B, ops, P)
    assert r.lignes["211"].montant == 62000
    assert r.frais == 2000


def test_pas_de_forfait_sans_recette():
    r = calculer_bien(2025, B, [op(1, "224", 10000)], P)
    assert r.lignes["222"].montant == 0
    assert r.resultat == -10000


def test_forfait_par_local():
    immeuble = Bien(id=1, nom="Immeuble", nb_locaux=3)
    r = calculer_bien(2025, immeuble, [op(1, "211", 100000)], P)
    assert r.lignes["222"].montant == 6000
