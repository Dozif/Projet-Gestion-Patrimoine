import pytest
from django.core.management import call_command
from django.urls import reverse

from fiscalite.models import ParametresAnnuels

pytestmark = pytest.mark.django_db


def test_export_csv(client_verifie):
    call_command("seed_demo")
    r = client_verifie.get(reverse("declaration:export_csv", args=[2025]))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/csv")
    assert "declaration-2044-2025.csv" in r["Content-Disposition"]
    lignes = r.content.decode("utf-8-sig").splitlines()
    assert lignes[0] == "Ligne;Libellé;T2 Les Tilleuls;T3 Centre;Total"
    assert "211;Loyers bruts encaissés;7440;9360;16800" in lignes
    assert ";Résultat foncier;3009;-3915;-906" in lignes
    assert "4BC;Déficit imputable sur le revenu global;906" in lignes


def test_export_sans_parametres(client_verifie):
    ParametresAnnuels.objects.filter(annee=2025).delete()
    assert client_verifie.get(reverse("declaration:export_csv", args=[2025])).status_code == 404
