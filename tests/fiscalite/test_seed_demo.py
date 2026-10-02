import pytest
from django.core.management import CommandError, call_command

from fiscalite.services import calculer_annee

pytestmark = pytest.mark.django_db


def test_donnees_de_demonstration_retrouvent_la_maquette():
    call_command("seed_demo")
    resultat, _ = calculer_annee(2025)
    assert [b.resultat for b in resultat.biens] == [300_900, -391_500]
    assert resultat.deficit.case_4bc == 90_600
    assert resultat.deficit.case_4bd == 355_000


def test_refuse_une_base_non_vide():
    call_command("seed_demo")
    with pytest.raises(CommandError, match="déjà des biens"):
        call_command("seed_demo")
