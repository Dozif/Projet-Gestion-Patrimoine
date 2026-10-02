from datetime import date

import pytest

from credit.models import Echeance, Pret
from fiscal import DeficitReportable as DR
from fiscalite.models import Configuration, DecompteCopropriete, DeficitAnterieur, ParametresAnnuels
from fiscalite.services import ParametresManquants, calculer_annee, deficits_au_debut_de
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db


def preparer_exemple_2025():
    config = Configuration.charger()
    config.premiere_annee = 2025
    config.save()
    t2, t3 = creer_bien("T2 Les Tilleuls"), creer_bien("T3 Centre")
    for bien, montants in ((t2, (744_000, 52_100, 14_800, 0, 81_200, 96_000)),
                           (t3, (936_000, 65_500, 17_500, 640_000, 104_500, 132_000))):
        loyer, honoraires, assurance, travaux, taxe, copro = montants
        creer_operation(bien, "loyer", loyer, date(2025, 6, 5))
        creer_operation(bien, "honoraires", honoraires, date(2025, 12, 31))
        creer_operation(bien, "assurance-pno", assurance, date(2025, 5, 2))
        if travaux:
            creer_operation(bien, "travaux", travaux, date(2025, 3, 12))
        creer_operation(bien, "taxe-fonciere", taxe, date(2025, 10, 15))
        creer_operation(bien, "provisions-copro", copro, date(2025, 1, 10))
        creer_operation(bien, "teom", 16_800, date(2025, 10, 15))
    for bien, interets in ((t2, 200_000), (t3, 377_000)):
        pret = Pret.objects.create(bien=bien, banque="Banque", capital_emprunte=1, date_debut=date(2015, 1, 5))
        Echeance.objects.create(pret=pret, date=date(2025, 6, 5), capital=61_245, interets=interets, assurance=18_000)
    DecompteCopropriete.objects.create(bien=t2, annee=2024, part_non_deductible=21_000)
    DecompteCopropriete.objects.create(bien=t3, annee=2024, part_non_deductible=29_000)
    DeficitAnterieur.objects.create(annee_origine=2022, montant=240_000)
    DeficitAnterieur.objects.create(annee_origine=2023, montant=115_000)


def test_exemple_complet_depuis_la_base():
    preparer_exemple_2025()
    resultat, contexte = calculer_annee(2025)
    assert [b.resultat for b in resultat.biens] == [300_900, -391_500]
    assert resultat.deficit.case_4bc == 90_600
    assert resultat.deficit.case_4bd == 355_000


def test_echeances_et_decomptes_tracables():
    preparer_exemple_2025()
    resultat, contexte = calculer_annee(2025)
    ligne_250 = resultat.biens[0].lignes["250"]
    assert ligne_250.montant == 218_000
    assert "échéance" in contexte.sources[ligne_250.explication.operation_ids[0]]
    ligne_230 = resultat.biens[0].lignes["230"]
    assert ligne_230.montant == 21_000
    assert "décompte 2024" in contexte.sources[ligne_230.explication.operation_ids[0]]


def test_deficits_tenus_a_jour_d_une_annee_sur_l_autre():
    config = Configuration.charger()
    config.premiere_annee = 2024
    config.save()
    DeficitAnterieur.objects.create(annee_origine=2022, montant=240_000)
    creer_operation(creer_bien(), "loyer", 100_000, date(2024, 6, 5))
    assert deficits_au_debut_de(2025) == (DR(2022, 142_000),)


def test_parametres_absents():
    ParametresAnnuels.objects.filter(annee=2025).delete()
    with pytest.raises(ParametresManquants, match="2025"):
        calculer_annee(2025)


def test_annee_anterieure_a_la_premiere_annee_geree():
    with pytest.raises(ValueError, match="première année"):
        calculer_annee(2020)
