"""Conversion entre saisie en euros et centimes entiers."""

import re
from decimal import Decimal

ESPACE_FINE = "\u202f"
_MONTANT = re.compile(r"-?\d+(\.\d{1,2})?")


def parse_euros(texte: str) -> int:
    """'1 234,56 €' -> 123456. Lève ValueError si le texte n'est pas un montant."""
    propre = texte
    for caractere in (" ", "\u00a0", ESPACE_FINE, "€"):
        propre = propre.replace(caractere, "")
    propre = propre.replace("−", "-").strip()
    if propre.count(",") == 1 and "." in propre:
        propre = propre.replace(".", "")
    propre = propre.replace(",", ".")
    if not _MONTANT.fullmatch(propre):
        raise ValueError(f"Montant invalide : {texte!r}")
    return int(Decimal(propre) * 100)


def format_euros(centimes: int) -> str:
    signe = "−" if centimes < 0 else ""
    euros, cts = divmod(abs(centimes), 100)
    groupes = f"{euros:,}".replace(",", ESPACE_FINE)
    return f"{signe}{groupes},{cts:02d} €" if cts else f"{signe}{groupes} €"


def centimes_vers_saisie(centimes: int) -> str:
    signe = "-" if centimes < 0 else ""
    euros, cts = divmod(abs(centimes), 100)
    return f"{signe}{euros},{cts:02d}"
