from datetime import date

import pytest
from django.urls import reverse

from operations.models import Operation, ReleveAgence
from operations.services import enregistrer_releve
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


def releve(bien, **kw):
    d = dict(bien=bien, periode=date(2025, 9, 1), date_versement=date(2025, 9, 5), loyer_brut=62_000,
             charges_recues=4_000, honoraires=4_340)
    d.update(kw)
    return ReleveAgence(**d)


def test_releve_genere_trois_operations():
    ops = enregistrer_releve(releve(creer_bien()))
    assert sorted((o.categorie.code, o.montant) for o in ops) == [
        ("charges-locataire", 4_000), ("honoraires", 4_340), ("loyer", 62_000)
    ]
    assert all(o.date_paiement == date(2025, 9, 5) for o in ops)


def test_releve_sans_honoraires_ni_charges():
    ops = enregistrer_releve(releve(creer_bien(), charges_recues=0, honoraires=0))
    assert [o.categorie.code for o in ops] == ["loyer"]


def test_modifier_un_releve_ne_cree_pas_de_doublon():
    r = releve(creer_bien())
    enregistrer_releve(r)
    r.loyer_brut = 63_000
    enregistrer_releve(r)
    assert Operation.objects.count() == 3
    assert Operation.objects.get(categorie__code="loyer").montant == 63_000


def test_saisie_d_un_releve_par_l_ecran(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("operations:creer_releve"), {
        "bien": b.pk, "periode": "2025-09", "date_versement": "2025-09-05", "loyer_brut": "620",
        "charges_recues": "40", "honoraires": "43,40", "commentaire": "",
    })
    assert r.status_code == 302
    assert Operation.objects.filter(releve__isnull=False).count() == 3


def test_honoraires_superieurs_aux_sommes_recues_refuses(client_verifie):
    b = creer_bien()
    r = client_verifie.post(reverse("operations:creer_releve"), {
        "bien": b.pk, "periode": "2025-09", "date_versement": "2025-09-05", "loyer_brut": "100",
        "charges_recues": "", "honoraires": "200", "commentaire": "",
    })
    assert r.status_code == 200
    assert not ReleveAgence.objects.exists()
