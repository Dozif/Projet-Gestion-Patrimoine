from datetime import date

import pytest
from django.urls import reverse

from credit.models import Echeance, Pret
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


@pytest.fixture
def pret():
    return Pret.objects.create(bien=creer_bien(), banque="Banque", capital_emprunte=1, date_debut=date(2015, 1, 5))


def donnees(**kw):
    d = {"date": "2025-03-05", "capital": "612,45", "interets": "173,20", "assurance": "", "frais": "15"}
    d.update(kw)
    return d


def test_ajout_manuel(client_verifie, pret):
    r = client_verifie.post(reverse("credit:ajouter_echeance", args=[pret.pk]), donnees())
    assert r.status_code == 302
    e = Echeance.objects.get()
    assert (e.capital, e.interets, e.assurance, e.frais) == (61_245, 17_320, 0, 1_500)


def test_date_deja_occupee(client_verifie, pret):
    Echeance.objects.create(pret=pret, date=date(2025, 3, 5), interets=1)
    r = client_verifie.post(reverse("credit:ajouter_echeance", args=[pret.pk]), donnees())
    assert r.status_code == 200
    assert "existe déjà" in r.content.decode()
    assert Echeance.objects.count() == 1


def test_modification(client_verifie, pret):
    e = Echeance.objects.create(pret=pret, date=date(2025, 3, 5), interets=1)
    url = reverse("credit:modifier_echeance", args=[pret.pk, e.pk])
    assert client_verifie.post(url, donnees(interets="200")).status_code == 302
    e.refresh_from_db()
    assert e.interets == 20_000


def test_suppression(client_verifie, pret):
    e = Echeance.objects.create(pret=pret, date=date(2025, 3, 5), interets=1)
    client_verifie.post(reverse("credit:supprimer_echeance", args=[pret.pk, e.pk]))
    assert not Echeance.objects.exists()
