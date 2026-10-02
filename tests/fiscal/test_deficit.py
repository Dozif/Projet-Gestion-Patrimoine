import pytest

from fiscal.deficit import appliquer_deficits
from fiscal.modeles import DeficitReportable as DR
from fiscal.modeles import ParametresAnnuels

P = ParametresAnnuels(annee=2025)


def test_benefice_sans_deficit_anterieur():
    d = appliquer_deficits(2025, 1_000_000, 300_000, 200_000, (), P)
    assert (d.case_4ba, d.case_4bb, d.case_4bc, d.case_4bd) == (500_000, 0, 0, 0)
    assert d.revenu_net_estime == 500_000
    assert d.deficits_apres == ()


def test_benefice_impute_les_deficits_les_plus_anciens_dabord():
    d = appliquer_deficits(2025, 1_000_000, 300_000, 200_000, (DR(2023, 150_000), DR(2020, 400_000)), P)
    assert d.case_4ba == 500_000
    assert d.case_4bd == 550_000
    assert d.imputations == (DR(2020, 400_000), DR(2023, 100_000))
    assert d.deficits_apres == (DR(2023, 50_000),)
    assert d.revenu_net_estime == 0


def test_deficit_du_aux_autres_charges_impute_sur_le_revenu_global():
    d = appliquer_deficits(2025, 1_680_000, 1_157_600, 613_000, (), P)
    assert (d.case_4ba, d.case_4bb, d.case_4bc) == (0, 0, 90_600)
    assert d.deficits_apres == ()


def test_deficit_plafonne_a_10700_euros():
    d = appliquer_deficits(2025, 1_000_000, 2_500_000, 200_000, (), P)
    assert d.case_4bc == 1_070_000
    assert d.case_4bb == 630_000
    assert d.deficits_apres == (DR(2025, 630_000),)


def test_part_due_aux_interets_seulement_reportable():
    d = appliquer_deficits(2025, 300_000, 100_000, 500_000, (), P)
    assert d.case_4bc == 100_000
    assert d.case_4bb == 200_000


def test_regularisation_superieure_aux_frais_borne_la_part_interets():
    d = appliquer_deficits(2025, 100_000, -50_000, 400_000, (), P)
    assert d.case_4bc == 0
    assert d.case_4bb == 250_000


def test_deficits_anterieurs_conserves_en_annee_deficitaire():
    anterieurs = (DR(2022, 240_000), DR(2023, 115_000))
    d = appliquer_deficits(2025, 1_680_000, 1_157_600, 613_000, anterieurs, P)
    assert d.case_4bd == 355_000
    assert d.imputations == ()
    assert d.deficits_apres == anterieurs


def test_deficit_expire_exclu():
    d = appliquer_deficits(2025, 500_000, 0, 0, (DR(2014, 100_000), DR(2015, 50_000)), P)
    assert d.deficits_expires == (DR(2014, 100_000),)
    assert d.case_4bd == 50_000
    assert d.imputations == (DR(2015, 50_000),)


def test_deficit_d_origine_non_anterieure_refuse():
    with pytest.raises(ValueError, match="antérieur"):
        appliquer_deficits(2025, 500_000, 0, 0, (DR(2025, 100_000),), P)
