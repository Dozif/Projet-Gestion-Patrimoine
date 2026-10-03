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
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    raise ErreurImport("Encodage du fichier non reconnu : exportez le tableau en CSV (UTF-8 ou Windows).")


def _separateur(texte: str) -> str:
    entete = next((ligne for ligne in texte.splitlines() if ligne.strip()), "")
    return max((";", "\t", ","), key=entete.count)


def _sans_lignes_vides_en_tete(texte: str) -> str:
    """Retire les lignes vides (ou faites uniquement de séparateurs) avant la ligne d'en-têtes."""
    lignes = texte.splitlines(keepends=True)
    while lignes and not lignes[0].strip(" \t\r\n;,"):
        lignes.pop(0)
    return "".join(lignes)


def _lire_entetes(texte: str) -> list[str]:
    texte = _sans_lignes_vides_en_tete(texte)
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


def _lire_echeancier(texte: str, colonnes: Colonnes) -> list[EcheanceLue]:
    sans_vides = _sans_lignes_vides_en_tete(texte)
    retirees = texte.count("\n") - sans_vides.count("\n")
    texte = sans_vides
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=_separateur(texte))
    entetes = [e.strip() for e in (lecteur.fieldnames or [])]
    lecteur.fieldnames = entetes
    voulues = [c for c in (colonnes.date, colonnes.capital, colonnes.interets, colonnes.assurance) if c]
    manquantes = [c for c in voulues if c not in entetes]
    if manquantes:
        raise ErreurImport(f"Colonnes introuvables : {', '.join(manquantes)}")
    lues = []
    dates_vues = set()
    for ligne in lecteur:
        numero = lecteur.line_num + retirees
        if all(not (v or "").strip() for k, v in ligne.items() if k is not None and isinstance(v, str | None)):
            continue
        if any(ligne[c] is None for c in voulues):
            raise ErreurImport(f"Ligne {numero} : colonnes manquantes.")
        try:
            lue = EcheanceLue(
                _date(ligne[colonnes.date] or ""),
                _montant(ligne[colonnes.capital]),
                _montant(ligne[colonnes.interets]),
                _montant(ligne[colonnes.assurance]) if colonnes.assurance else 0,
            )
        except ValueError as erreur:
            raise ErreurImport(f"Ligne {numero} : {erreur}") from None
        if lue.date in dates_vues:
            raise ErreurImport(f"Ligne {numero} : échéance du {lue.date:%d/%m/%Y} en double.")
        dates_vues.add(lue.date)
        lues.append(lue)
    if not lues:
        raise ErreurImport("Aucune échéance trouvée dans le fichier.")
    return lues


def lire_entetes(texte: str) -> list[str]:
    try:
        return _lire_entetes(texte)
    except csv.Error as erreur:
        raise ErreurImport(f"Fichier CSV illisible : {erreur}.") from None


def lire_echeancier(texte: str, colonnes: Colonnes) -> list[EcheanceLue]:
    try:
        return _lire_echeancier(texte, colonnes)
    except csv.Error as erreur:
        raise ErreurImport(f"Fichier CSV illisible : {erreur}.") from None
