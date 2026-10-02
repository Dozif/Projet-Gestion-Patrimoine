"""Structures de données d'entrée et de sortie du moteur fiscal (montants en centimes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Nature(StrEnum):
    RECETTE_IMPOSABLE = "RECETTE_IMPOSABLE"
    RECETTE_NON_IMPOSABLE = "RECETTE_NON_IMPOSABLE"
    CHARGE_DEDUCTIBLE = "CHARGE_DEDUCTIBLE"
    CHARGE_NON_DEDUCTIBLE = "CHARGE_NON_DEDUCTIBLE"
    INTERETS = "INTERETS"


LIGNES_RECETTES = ("211", "212", "213", "214")
LIGNES_FRAIS_SAISIES = ("221", "223", "224", "225", "226", "227", "229")
LIGNE_FORFAIT = "222"
LIGNE_REGULARISATION = "230"
LIGNE_INTERETS = "250"

_LIGNES_PAR_NATURE: dict[Nature, tuple[str | None, ...]] = {
    Nature.RECETTE_IMPOSABLE: LIGNES_RECETTES,
    Nature.CHARGE_DEDUCTIBLE: LIGNES_FRAIS_SAISIES + (LIGNE_REGULARISATION,),
    Nature.INTERETS: (LIGNE_INTERETS,),
    Nature.RECETTE_NON_IMPOSABLE: (None,),
    Nature.CHARGE_NON_DEDUCTIBLE: (None,),
}


@dataclass(frozen=True)
class Operation:
    """Un encaissement ou un paiement. La ligne 230 (régularisation) vient en déduction des frais."""

    id: int
    bien_id: int
    date_paiement: date
    montant: int
    nature: Nature
    ligne_2044: str | None
    libelle: str = ""

    def __post_init__(self) -> None:
        if self.montant <= 0:
            raise ValueError("Le montant d'une opération doit être strictement positif (en centimes).")
        if self.ligne_2044 not in _LIGNES_PAR_NATURE[self.nature]:
            raise ValueError(
                f"Ligne 2044 {self.ligne_2044!r} incompatible avec la nature {self.nature.value}."
            )


@dataclass(frozen=True)
class Bien:
    id: int
    nom: str
    regime: str = "FONCIER_REEL"
    nb_locaux: int = 1


@dataclass(frozen=True)
class DeficitReportable:
    annee_origine: int
    montant: int


@dataclass(frozen=True)
class ParametresAnnuels:
    annee: int
    plafond_imputation_revenu_global: int = 1_070_000
    forfait_gestion_par_local: int = 2_000


@dataclass(frozen=True)
class Explication:
    regle: str
    source: str
    operation_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class LigneCalculee:
    code: str
    libelle: str
    montant: int
    explication: Explication


def en_euros(centimes: int) -> int:
    """Arrondit des centimes à l'euro le plus proche (0,50 € arrondi à l'euro supérieur)."""
    quotient, reste = divmod(abs(centimes), 100)
    euros = quotient + (1 if reste >= 50 else 0)
    return -euros if centimes < 0 else euros
