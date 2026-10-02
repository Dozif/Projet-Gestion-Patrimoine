import pytest
from django.urls import reverse

import fiscal
from fiscalite.models import Configuration, DecompteCopropriete, DeficitAnterieur, ParametresAnnuels
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def test_parametres_initiaux():
    p = ParametresAnnuels.objects.get(annee=2025)
    assert p.vers_fiscal() == fiscal.ParametresAnnuels(
        annee=2025, plafond_imputation_revenu_global=1_070_000, forfait_gestion_par_local=2_000
    )
    assert ParametresAnnuels.objects.filter(annee__in=[2024, 2025, 2026]).count() == 3


def test_saisie_d_un_decompte_de_copropriete(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("fiscalite:copropriete"), {
        "bien": b.pk, "annee": "2024", "part_non_deductible": "210", "commentaire": "",
    })
    assert r.status_code == 302
    assert DecompteCopropriete.objects.get().part_non_deductible == 21_000


def test_decompte_en_double_refuse(client_verifie):
    b = creer_bien()
    DecompteCopropriete.objects.create(bien=b, annee=2024, part_non_deductible=1)
    r = client_verifie.post(reverse("fiscalite:copropriete"), {
        "bien": b.pk, "annee": "2024", "part_non_deductible": "210", "commentaire": "",
    })
    assert r.status_code == 200
    assert DecompteCopropriete.objects.count() == 1


def test_deficit_doit_etre_anterieur_a_la_premiere_annee(client_verifie):
    r = client_verifie.post(reverse("fiscalite:deficits"), {
        "deficit-annee_origine": "2025", "deficit-montant": "2 400", "deficit": "1",
    })
    assert r.status_code == 200
    assert "antérieur" in r.content.decode()
    assert not DeficitAnterieur.objects.exists()


def test_changer_la_premiere_annee_puis_saisir_un_deficit(client_verifie):
    client_verifie.post(reverse("fiscalite:deficits"), {"config-premiere_annee": "2024", "configuration": "1"})
    assert Configuration.charger().premiere_annee == 2024
    r = client_verifie.post(reverse("fiscalite:deficits"), {
        "deficit-annee_origine": "2022", "deficit-montant": "2 400", "deficit": "1",
    })
    assert r.status_code == 302
    assert DeficitAnterieur.objects.get().montant == 240_000
