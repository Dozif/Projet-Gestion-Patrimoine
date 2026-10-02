from datetime import date

import pytest

from fiscal.modeles import Bien, Nature, Operation, en_euros


def op(**kw):
    base = dict(
        id=1, bien_id=1, date_paiement=date(2025, 1, 5), montant=62000,
        nature=Nature.RECETTE_IMPOSABLE, ligne_2044="211",
    )
    base.update(kw)
    return Operation(**base)


def test_operation_valide():
    assert op().montant == 62000


@pytest.mark.parametrize("montant", [0, -100])
def test_montant_doit_etre_strictement_positif(montant):
    with pytest.raises(ValueError, match="strictement positif"):
        op(montant=montant)


def test_ligne_incompatible_avec_la_nature():
    with pytest.raises(ValueError, match="incompatible"):
        op(nature=Nature.CHARGE_DEDUCTIBLE, ligne_2044="211")


def test_forfait_222_non_saisissable():
    with pytest.raises(ValueError, match="incompatible"):
        op(nature=Nature.CHARGE_DEDUCTIBLE, ligne_2044="222")


def test_non_imposable_et_non_deductible_sans_ligne():
    assert op(nature=Nature.RECETTE_NON_IMPOSABLE, ligne_2044=None).ligne_2044 is None
    assert op(nature=Nature.CHARGE_NON_DEDUCTIBLE, ligne_2044=None).ligne_2044 is None
    with pytest.raises(ValueError, match="incompatible"):
        op(nature=Nature.RECETTE_NON_IMPOSABLE, ligne_2044="211")


def test_regularisation_et_interets():
    assert op(nature=Nature.CHARGE_DEDUCTIBLE, ligne_2044="230").ligne_2044 == "230"
    assert op(nature=Nature.INTERETS, ligne_2044="250").ligne_2044 == "250"


@pytest.mark.parametrize("centimes,euros", [(15050, 151), (15049, 150), (-15050, -151), (0, 0)])
def test_en_euros_arrondi_au_plus_proche(centimes, euros):
    assert en_euros(centimes) == euros


def test_montant_decimal_refuse():
    with pytest.raises(ValueError, match="entier"):
        op(montant=12.5)


def test_nature_inconnue_refusee():
    with pytest.raises(ValueError, match="Nature inconnue"):
        op(nature="BIDON")


def test_nature_en_texte_convertie():
    assert op(nature="RECETTE_IMPOSABLE").nature is Nature.RECETTE_IMPOSABLE
    with pytest.raises(ValueError, match="incompatible"):
        op(nature="CHARGE_DEDUCTIBLE", ligne_2044="211")


@pytest.mark.parametrize("nb", [0, -2])
def test_bien_sans_local_refuse(nb):
    with pytest.raises(ValueError, match="local"):
        Bien(id=1, nom="T2", nb_locaux=nb)
