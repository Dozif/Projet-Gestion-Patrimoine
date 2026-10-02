import pytest
from django.template import Context, Template
from django.urls import reverse

from commun.annees import annee_demandee


@pytest.mark.parametrize(
    "requete,attendu", [("?annee=2025", 2025), ("?annee=abc", 2026), ("?annee=99999", 2026), ("", 2026)]
)
def test_annee_demandee(rf, requete, attendu):
    assert annee_demandee(rf.get("/" + requete), 2026) == attendu


@pytest.mark.django_db
def test_liste_des_operations_avec_une_annee_farfelue(client_verifie):
    assert client_verifie.get(reverse("operations:liste") + "?annee=99999").status_code == 200


def test_filtre_euros_entiers():
    gabarit = Template("{% load montants %}{{ a|euros_entiers }}|{{ b|euros_entiers }}|{{ c|euros_entiers }}")
    assert gabarit.render(Context({"a": 15050, "b": -90600, "c": None})) == "151 €|−906 €|—"
