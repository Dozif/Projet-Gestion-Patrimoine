from datetime import date

import pytest
from django.core.management import call_command

from biens.models import Bail, Bien, Locataire
from declaration.suivi import alerte_loyers, alertes_pinel, etat_loyers, resume_pinel
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db
AUJOURD_HUI = date(2026, 10, 2)


def bien_loue():
    b = creer_bien()
    Bail.objects.create(
        bien=b, locataire=Locataire.objects.create(nom="L"), date_debut=date(2023, 9, 1), loyer_hc=62_000
    )
    return b


def test_etat_des_loyers_mois_par_mois():
    b = bien_loue()
    for mois in range(1, 9):
        creer_operation(b, "loyer", 62_000, date(2026, mois, 5))
    etats = [e["etat"] for e in etat_loyers(b, 2026, AUJOURD_HUI)]
    assert etats == ["encaisse"] * 8 + ["manquant"] + ["a_venir"] * 3


def test_mois_sans_bail():
    etats = etat_loyers(creer_bien(), 2026, AUJOURD_HUI)
    assert etats[0]["etat"] == "sans_bail"
    assert etats[0]["initiale"] == "J"


def test_alerte_loyer_manquant():
    b = bien_loue()
    etats = etat_loyers(b, 2026, AUJOURD_HUI)
    assert "septembre" in alerte_loyers(b, etats)["texte"]
    assert alerte_loyers(b, [e | {"etat": "encaisse"} for e in etats]) is None


@pytest.fixture
def t2():
    call_command("seed_demo")
    return Bien.objects.get(nom="T2 Les Tilleuls")


def test_resume_pinel_avec_plafond(t2):
    resume = resume_pinel(t2, 2025, AUJOURD_HUI, {"A": 1239})
    assert resume["reduction_annee"] == 168_000
    assert resume["pourcentage"] == 95
    assert (resume["loyer"], resume["plafond"], resume["depasse"]) == (62_000, 65_500, False)


def test_resume_pinel_sans_plafond_renseigne(t2):
    resume = resume_pinel(t2, 2025, AUJOURD_HUI, {})
    assert resume["plafond"] is None
    assert resume["depasse"] is False


def test_loyer_au_dessus_du_plafond(t2):
    Bail.objects.filter(bien=t2).update(loyer_hc=70_000)
    resume = resume_pinel(t2, 2025, AUJOURD_HUI, {"A": 1239})
    assert resume["depasse"]
    assert any("plafond" in a["titre"] for a in alertes_pinel(resume, AUJOURD_HUI))


def test_fin_d_engagement_proche(t2):
    alertes = alertes_pinel(resume_pinel(t2, 2026, AUJOURD_HUI, {}), AUJOURD_HUI)
    assert any("31/12/2026" in a["titre"] for a in alertes)
    assert resume_pinel(creer_bien("Sans Pinel"), 2026, AUJOURD_HUI, {}) is None
