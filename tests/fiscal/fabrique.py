from datetime import date
from itertools import count

from fiscal.modeles import LIGNE_INTERETS, LIGNES_RECETTES, Nature, Operation

_ids = count(1)


def op(bien_id, code, montant, *, nature=None, annee=2025, mois=1, libelle=""):
    if nature is None:
        if code is None:
            raise ValueError("Préciser la nature d'une opération sans ligne 2044.")
        if code in LIGNES_RECETTES:
            nature = Nature.RECETTE_IMPOSABLE
        elif code == LIGNE_INTERETS:
            nature = Nature.INTERETS
        else:
            nature = Nature.CHARGE_DEDUCTIBLE
    return Operation(
        id=next(_ids), bien_id=bien_id, date_paiement=date(annee, mois, 15),
        montant=montant, nature=nature, ligne_2044=code, libelle=libelle,
    )
