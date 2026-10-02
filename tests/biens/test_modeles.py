from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

import fiscal
from biens.models import Bail, Bien, EngagementPinel, Locataire, PeriodePinel
from fiscal.pinel import reduction_annee
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def test_bien_vers_fiscal():
    b = creer_bien(nb_locaux=2)
    assert b.vers_fiscal() == fiscal.Bien(id=b.pk, nom="T2 Les Tilleuls", regime="FONCIER_REEL", nb_locaux=2)


def test_engagement_pinel_vers_fiscal_calcule_la_reduction():
    e = EngagementPinel.objects.create(
        bien=creer_bien(), date_mise_en_location=date(2015, 1, 1), duree_annees=12, zone="A",
        prix_revient=16_800_000, surface_habitable=Decimal("45"),
    )
    PeriodePinel.objects.create(engagement=e, annee_debut=2015, annee_fin=2023, taux_annuel=Decimal("2"))
    PeriodePinel.objects.create(engagement=e, annee_debut=2024, annee_fin=2026, taux_annuel=Decimal("1"))
    assert reduction_annee(e.vers_fiscal(), 2026) == 168_000


def test_bail_en_cours():
    b = creer_bien()
    loc = Locataire.objects.create(nom="Locataire")
    ancien = Bail.objects.create(
        bien=b, locataire=loc, date_debut=date(2020, 1, 1), date_fin=date(2023, 6, 30), loyer_hc=60_000
    )
    actuel = Bail.objects.create(bien=b, locataire=loc, date_debut=date(2023, 7, 1), loyer_hc=62_000)
    assert b.bail_en_cours(date(2025, 1, 1)) == actuel
    assert b.bail_en_cours(date(2021, 1, 1)) == ancien
    assert b.bail_en_cours(date(2019, 1, 1)) is None


def test_bail_qui_finit_avant_de_commencer_refuse():
    bail = Bail(
        bien=creer_bien(), locataire=Locataire.objects.create(nom="L"), date_debut=date(2024, 1, 1),
        date_fin=date(2023, 1, 1), loyer_hc=1,
    )
    with pytest.raises(ValidationError):
        bail.full_clean()


def test_bien_sans_local_refuse():
    with pytest.raises(ValidationError):
        Bien(nom="X", surface_habitable=Decimal("10"), nb_locaux=0).full_clean()
