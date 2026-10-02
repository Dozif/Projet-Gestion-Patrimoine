from decimal import Decimal

from biens.models import Bien


def creer_bien(nom="T2 Les Tilleuls", **kw):
    kw.setdefault("surface_habitable", Decimal("45"))
    kw.setdefault("prix_revient", 16_800_000)
    return Bien.objects.create(nom=nom, **kw)
