import pytest

from fiscal.calculateur import CalculateurFoncierReel, calculateur_pour
from fiscal.modeles import Bien, ParametresAnnuels
from fiscal.modeles import DeficitReportable as DR
from tests.fiscal.fabrique import op

P = ParametresAnnuels(annee=2025)
T2 = Bien(id=1, nom="T2 Les Tilleuls")
T3 = Bien(id=2, nom="T3 Centre")


def operations_2025():
    return [
        op(1, "211", 744000), op(1, "221", 52100), op(1, "223", 14800), op(1, "227", 81200),
        op(1, "229", 96000), op(1, "230", 21000), op(1, "250", 218000),
        op(2, "211", 936000), op(2, "221", 65500), op(2, "223", 17500), op(2, "224", 640000),
        op(2, "227", 104500), op(2, "229", 132000), op(2, "230", 29000), op(2, "250", 395000),
    ]


def test_exemple_complet_deux_biens_un_deficitaire():
    anterieurs = (DR(2022, 240_000), DR(2023, 115_000))
    r = CalculateurFoncierReel().calculer(2025, [T2, T3], operations_2025(), anterieurs, P)
    assert [b.resultat for b in r.biens] == [300_900, -391_500]
    assert (r.total_recettes, r.total_frais, r.total_interets) == (1_680_000, 1_157_600, 613_000)
    assert r.resultat_global == -90_600
    assert r.deficit.case_4bc == 90_600
    assert r.deficit.case_4bb == 0
    assert r.deficit.case_4bd == 355_000
    assert any("31/12/2028" in a for a in r.alertes)


def test_biens_d_un_autre_regime_ignores():
    lmnp = Bien(id=3, nom="Studio meublé", regime="LMNP_REEL")
    ops = operations_2025() + [op(3, "211", 500000)]
    r = CalculateurFoncierReel().calculer(2025, [T2, T3, lmnp], ops, (), P)
    assert [b.bien_id for b in r.biens] == [1, 2]
    assert r.total_recettes == 1_680_000


def test_parametres_d_une_autre_annee_refuses():
    with pytest.raises(ValueError, match="2024"):
        CalculateurFoncierReel().calculer(2025, [T2], [], (), ParametresAnnuels(annee=2024))


def test_alerte_deficit_en_derniere_annee_et_deficit_expire():
    r = CalculateurFoncierReel().calculer(
        2025, [T3], [op(2, "224", 100000)], (DR(2014, 30_000), DR(2015, 50_000)), P
    )
    assert any("2015" in a and "dernière année" in a for a in r.alertes)
    assert any("2014" in a and "expiré" in a for a in r.alertes)


def test_registre_des_regimes():
    assert isinstance(calculateur_pour("FONCIER_REEL"), CalculateurFoncierReel)
    with pytest.raises(NotImplementedError, match="LMNP_REEL"):
        calculateur_pour("LMNP_REEL")
