import pytest
from django.urls import reverse

from biens.models import Bail, Bien, EngagementPinel
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def donnees_pinel(periodes):
    d = {
        "date_mise_en_location": "2015-01-01", "duree_annees": "12", "zone": "A",
        "prix_revient": "168 000", "surface_habitable": "45",
        "periodes-TOTAL_FORMS": str(len(periodes)), "periodes-INITIAL_FORMS": "0",
        "periodes-MIN_NUM_FORMS": "0", "periodes-MAX_NUM_FORMS": "1000",
    }
    for i, (debut, fin, taux) in enumerate(periodes):
        d[f"periodes-{i}-annee_debut"] = str(debut)
        d[f"periodes-{i}-annee_fin"] = str(fin)
        d[f"periodes-{i}-taux_annuel"] = str(taux)
    return d


def test_creation_d_un_bien_avec_prix_en_euros(client_verifie):
    r = client_verifie.post(reverse("biens:creer"), {
        "nom": "T2 Les Tilleuls", "surface_habitable": "45", "surface_annexes": "7",
        "prix_revient": "168 000", "regime": "FONCIER_REEL", "nb_locaux": "1", "actif": "on",
    })
    assert r.status_code == 302
    assert Bien.objects.get().prix_revient == 16_800_000


def test_fiche_affiche_le_prix_formate(client_verifie):
    b = creer_bien()
    assert "168 000 €" in client_verifie.get(b.get_absolute_url()).content.decode()


def test_liste_des_biens(client_verifie):
    creer_bien("T3 Centre")
    assert "T3 Centre" in client_verifie.get(reverse("biens:liste")).content.decode()


def test_periodes_pinel_qui_se_chevauchent_refusees(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("biens:pinel", args=[b.pk]), donnees_pinel([(2015, 2023, 2), (2023, 2026, 1)]))
    assert r.status_code == 200
    assert "chevauchent" in r.content.decode()
    assert not EngagementPinel.objects.exists()


def test_engagement_pinel_valide_enregistre(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("biens:pinel", args=[b.pk]), donnees_pinel([(2015, 2023, 2), (2024, 2026, 1)]))
    assert r.status_code == 302
    assert EngagementPinel.objects.get(bien=b).periodes.count() == 2


def test_creation_d_un_bail_avec_son_locataire(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("biens:creer_bail", args=[b.pk]), {
        "locataire-nom": "Locataire A", "bail-date_debut": "2023-09-01", "bail-loyer_hc": "620",
        "bail-provision_charges": "40", "bail-depot_garantie": "",
    })
    assert r.status_code == 302
    bail = Bail.objects.get()
    assert (bail.loyer_hc, bail.provision_charges, bail.depot_garantie) == (62_000, 4_000, 0)
    assert bail.locataire.nom == "Locataire A"


def test_bien_inexistant(client_verifie):
    assert client_verifie.get(reverse("biens:detail", args=[999])).status_code == 404
