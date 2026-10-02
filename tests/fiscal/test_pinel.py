from datetime import date
from decimal import Decimal as D

import pytest

from fiscal.pinel import (
    EngagementPinel,
    PeriodePinel,
    base_reduction,
    fin_engagement,
    plafond_loyer_mensuel,
    reduction_annee,
    reduction_cumulee,
    reduction_totale,
)

PERIODES = (PeriodePinel(2015, 2023, D("2")), PeriodePinel(2024, 2026, D("1")))


def engagement(prix=16_800_000, surface=D("45"), periodes=PERIODES, debut=date(2015, 1, 1), duree=12):
    return EngagementPinel(debut, duree, prix, surface, periodes)


def test_base_plafonnee_a_300000_euros():
    assert base_reduction(engagement(prix=35_000_000, surface=D("80"))) == 30_000_000


def test_base_plafonnee_a_5500_euros_le_m2():
    assert base_reduction(engagement(prix=29_000_000, surface=D("50"))) == 27_500_000


def test_reduction_annuelle_et_cumuls():
    e = engagement()
    assert reduction_annee(e, 2020) == 336_000
    assert reduction_annee(e, 2026) == 168_000
    assert reduction_annee(e, 2027) == 0
    assert reduction_cumulee(e, 2025) == 3_360_000
    assert reduction_totale(e) == 3_528_000


def test_periodes_qui_se_chevauchent_refusees():
    with pytest.raises(ValueError, match="chevauch"):
        engagement(periodes=(PeriodePinel(2015, 2023, D("2")), PeriodePinel(2023, 2026, D("1"))))


def test_duree_invalide_refusee():
    with pytest.raises(ValueError, match="6, 9 ou 12"):
        engagement(duree=10)


@pytest.mark.parametrize(
    "debut,duree,fin",
    [(date(2015, 3, 1), 12, date(2027, 2, 28)), (date(2016, 2, 29), 9, date(2025, 2, 28))],
)
def test_fin_engagement(debut, duree, fin):
    assert fin_engagement(engagement(debut=debut, duree=duree)) == fin


def test_plafond_de_loyer_avec_coefficient_arrondi():
    assert plafond_loyer_mensuel(1239, D("45"), D("7")) == 65_500


def test_coefficient_plafonne_a_1_2():
    assert plafond_loyer_mensuel(1000, D("20"), D("0")) == 24_000


def test_annexes_plafonnees_a_8_m2():
    assert plafond_loyer_mensuel(1000, D("60"), D("30")) == plafond_loyer_mensuel(1000, D("60"), D("16"))
