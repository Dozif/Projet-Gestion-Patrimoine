import pytest
from django import forms
from django.template import Context, Template

from commun.forms import MontantField
from commun.montants import format_euros, parse_euros


@pytest.mark.parametrize(
    "texte,centimes",
    [("1 234,56", 123456), ("1234.56", 123456), ("12,5", 1250), ("1.234,56", 123456),
     ("1\u202f234,56 €", 123456), ("-5", -500), ("0", 0)],
)
def test_parse_euros(texte, centimes):
    assert parse_euros(texte) == centimes


@pytest.mark.parametrize("texte", ["abc", "12,345", ""])
def test_parse_euros_invalide(texte):
    with pytest.raises(ValueError):
        parse_euros(texte)


@pytest.mark.parametrize(
    "centimes,texte",
    [(744000, "7\u202f440 €"), (4340, "43,40 €"), (-90600, "−906 €"), (0, "0 €"),
     (123456789, "1\u202f234\u202f567,89 €")],
)
def test_format_euros(centimes, texte):
    assert format_euros(centimes) == texte


def test_champ_montant_convertit_en_centimes():
    assert MontantField().clean("1 234,56") == 123456


def test_champ_montant_refuse_zero_par_defaut():
    with pytest.raises(forms.ValidationError, match="supérieur à zéro"):
        MontantField().clean("0")


def test_champ_montant_message_si_invalide():
    with pytest.raises(forms.ValidationError, match="1 234,56"):
        MontantField().clean("abc")


def test_champ_montant_sans_minimum_accepte_negatif():
    assert MontantField(minimum=None).clean("-5") == -500


def test_champ_montant_vide():
    assert MontantField(required=False).clean("") is None
    assert MontantField(required=False, minimum=0, valeur_si_vide=0).clean("") == 0


@pytest.mark.parametrize("centimes,saisie", [(123456, "1234,56"), (-500, "-5,00")])
def test_champ_montant_reaffiche_en_saisie(centimes, saisie):
    assert MontantField().prepare_value(centimes) == saisie


def test_filtre_euros():
    gabarit = Template("{% load montants %}{{ a|euros }}|{{ b|euros }}")
    assert gabarit.render(Context({"a": 4340, "b": None})) == "43,40 €|—"
