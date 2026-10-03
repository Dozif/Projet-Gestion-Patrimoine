import csv
import io

import pytest
from django.core.management import call_command
from django.urls import reverse

from biens.models import Bien

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("suffixe", ["csv", "figer", "defiger"])
def test_annee_demesuree_donne_404(client_verifie, suffixe):
    url = f"/declaration/{10**30}/{suffixe}/"
    r = client_verifie.post(url) if suffixe != "csv" else client_verifie.get(url)
    assert r.status_code == 404


def test_nom_de_bien_en_forme_de_formule_neutralise(client_verifie):
    call_command("seed_demo")
    Bien.objects.filter(nom="T2 Les Tilleuls").update(nom="=HYPERLINK(\"http://x\")")
    texte = client_verifie.get(reverse("declaration:export_csv", args=[2025])).content.decode("utf-8-sig")
    entetes = next(csv.reader(io.StringIO(texte), delimiter=";"))
    assert "'=HYPERLINK(\"http://x\")" in entetes
