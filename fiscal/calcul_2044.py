"""Calcul des lignes de la déclaration 2044 pour un bien et une année."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .modeles import (
    LIGNE_FORFAIT,
    LIGNE_INTERETS,
    LIGNE_REGULARISATION,
    LIGNES_FRAIS_SAISIES,
    LIGNES_RECETTES,
    Bien,
    Explication,
    LigneCalculee,
    Nature,
    Operation,
    ParametresAnnuels,
)

NOTICE = "Notice de la déclaration 2044"

# code -> (libellé, règle, source)
LIGNES: dict[str, tuple[str, str, str]] = {
    "211": ("Loyers bruts encaissés", "Loyers hors charges réellement encaissés dans l'année.", NOTICE),
    "212": ("Dépenses du propriétaire mises à la charge du locataire",
            "Dépenses incombant normalement au propriétaire et payées par le locataire.", NOTICE),
    "213": ("Subventions et indemnités pour travaux",
            "Subventions ANAH et indemnités couvrant des charges déductibles.",
            NOTICE),
    "214": ("Autres recettes", "Indemnités d'assurance pour pertes de loyers et autres recettes.", NOTICE),
    "215": ("Total des recettes", "Somme des lignes 211 à 214.", NOTICE),
    "221": ("Frais d'administration et de gestion",
            "Honoraires d'agence, frais de procédure, rémunération d'un gardien : montant réel.",
            "BOFiP BOI-RFPI-BASE-20-10"),
    "222": ("Autres frais de gestion",
            "Forfait par local loué dans l'année (correspondance, téléphone, etc.).", NOTICE),
    "223": ("Primes d'assurance",
            "Assurance propriétaire non occupant, garantie des loyers impayés.", NOTICE),
    "224": ("Travaux de réparation, d'entretien et d'amélioration",
            "Déductibles sauf travaux de construction, de reconstruction ou d'agrandissement.",
            "BOFiP BOI-RFPI-BASE-20-30"),
    "225": ("Charges récupérables non récupérées",
            "Charges récupérables restées à la charge du propriétaire au départ du locataire.", NOTICE),
    "226": ("Indemnités d'éviction et frais de relogement",
            "Indemnités versées pour libérer le local.", NOTICE),
    "227": ("Taxes foncières",
            "Taxe foncière déductible, hors taxe d'enlèvement des ordures ménagères.", NOTICE),
    "229": ("Provisions pour charges de copropriété", "Provisions versées au syndic dans l'année.", NOTICE),
    "230": ("Régularisation des provisions de l'année précédente",
            "Part non déductible des provisions déduites l'année précédente, d'après le décompte du syndic : "
            "vient en diminution des frais.", NOTICE),
    "240": ("Total des frais et charges", "Lignes 221 à 229, moins la ligne 230.", NOTICE),
    "250": ("Intérêts et frais d'emprunt",
            "Intérêts, assurance emprunteur et frais d'emprunt ; le capital remboursé n'est pas déductible.",
            "BOFiP BOI-RFPI-BASE-20-80"),
}


@dataclass(frozen=True)
class ResultatBien:
    bien_id: int
    lignes: dict[str, LigneCalculee]
    resultat: int

    @property
    def recettes(self) -> int:
        return self.lignes["215"].montant

    @property
    def frais(self) -> int:
        return self.lignes["240"].montant

    @property
    def interets(self) -> int:
        return self.lignes[LIGNE_INTERETS].montant


def _ligne(code: str, montant: int, operation_ids: tuple[int, ...] = ()) -> LigneCalculee:
    libelle, regle, source = LIGNES[code]
    return LigneCalculee(code, libelle, montant, Explication(regle, source, operation_ids))


def calculer_bien(
    annee: int, bien: Bien, operations: Iterable[Operation], params: ParametresAnnuels
) -> ResultatBien:
    ops = [o for o in operations if o.bien_id == bien.id and o.date_paiement.year == annee]

    def somme(code: str, nature: Nature) -> LigneCalculee:
        retenues = [o for o in ops if o.ligne_2044 == code and o.nature == nature]
        return _ligne(code, sum(o.montant for o in retenues), tuple(o.id for o in retenues))

    lignes: dict[str, LigneCalculee] = {}
    for code in LIGNES_RECETTES:
        lignes[code] = somme(code, Nature.RECETTE_IMPOSABLE)
    lignes["215"] = _ligne("215", sum(lignes[c].montant for c in LIGNES_RECETTES))

    a_des_recettes = any(o.nature == Nature.RECETTE_IMPOSABLE for o in ops)
    forfait = params.forfait_gestion_par_local * bien.nb_locaux if a_des_recettes else 0
    lignes[LIGNE_FORFAIT] = _ligne(LIGNE_FORFAIT, forfait)
    for code in LIGNES_FRAIS_SAISIES + (LIGNE_REGULARISATION,):
        lignes[code] = somme(code, Nature.CHARGE_DEDUCTIBLE)
    frais = (
        sum(lignes[c].montant for c in LIGNES_FRAIS_SAISIES)
        + forfait
        - lignes[LIGNE_REGULARISATION].montant
    )
    lignes["240"] = _ligne("240", frais)

    lignes[LIGNE_INTERETS] = somme(LIGNE_INTERETS, Nature.INTERETS)

    resultat = lignes["215"].montant - frais - lignes[LIGNE_INTERETS].montant
    return ResultatBien(bien.id, lignes, resultat)
