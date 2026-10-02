from decimal import Decimal

from biens.models import Bien
from operations.models import Categorie, Operation


def creer_bien(nom="T2 Les Tilleuls", **kw):
    kw.setdefault("surface_habitable", Decimal("45"))
    kw.setdefault("prix_revient", 16_800_000)
    return Bien.objects.create(nom=nom, **kw)


def creer_operation(bien, code, montant, jour, libelle=None, **kw):
    return Operation.objects.create(
        bien=bien, categorie=Categorie.objects.get(code=code), date_paiement=jour, montant=montant,
        libelle=libelle or code, **kw,
    )
