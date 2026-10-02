"""Lecture d'un tableau d'amortissement exporté par la banque (CSV)."""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

from commun.montants import parse_euros

FORMATS_DATE = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y")


class ErreurImport(ValueError):
    pass


@dataclass(frozen=True)
class Colonnes:
    date: str
    capital: str
    interets: str
    assurance: str = ""


@dataclass(frozen=True)
class EcheanceLue:
    date: date
    capital: int
    interets: int
    assurance: int


def decoder(contenu: bytes) -> str:
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenu.decode("cp1252")


def _separateur(texte: str) -> str:
    entete = next((ligne for ligne in texte.splitlines() if ligne.strip()), "")
    return max((";", "\t", ","), key=entete.count)


def lire_entetes(texte: str) -> list[str]:
    lecteur = csv.reader(io.StringIO(texte), delimiter=_separateur(texte))
    for ligne in lecteur:
        if any(cellule.strip() for cellule in ligne):
            return [cellule.strip() for cellule in ligne]
    raise ErreurImport("Le fichier est vide.")


def _date(valeur: str) -> date:
    for format_date in FORMATS_DATE:
        try:
            return datetime.strptime(valeur.strip(), format_date).date()
        except ValueError:
            continue
    raise ValueError(f"date invalide {valeur!r}")


def _montant(valeur: str | None) -> int:
    valeur = (valeur or "").strip()
    return 0 if not valeur else abs(parse_euros(valeur))


def lire_echeancier(texte: str, colonnes: Colonnes) -> list[EcheanceLue]:
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=_separateur(texte))
    entetes = [e.strip() for e in (lecteur.fieldnames or [])]
    lecteur.fieldnames = entetes
    voulues = [c for c in (colonnes.date, colonnes.capital, colonnes.interets, colonnes.assurance) if c]
    manquantes = [c for c in voulues if c not in entetes]
    if manquantes:
        raise ErreurImport(f"Colonnes introuvables : {', '.join(manquantes)}")
    lues = []
    for ligne in lecteur:
        if all(not (v or "").strip() for k, v in ligne.items() if k is not None and isinstance(v, str | None)):
            continue
        try:
            lues.append(EcheanceLue(
                _date(ligne[colonnes.date] or ""),
                _montant(ligne[colonnes.capital]),
                _montant(ligne[colonnes.interets]),
                _montant(ligne[colonnes.assurance]) if colonnes.assurance else 0,
            ))
        except ValueError as erreur:
            raise ErreurImport(f"Ligne {lecteur.line_num} : {erreur}") from None
    if not lues:
        raise ErreurImport("Aucune échéance trouvée dans le fichier.")
    return lues
