"""Dispositif Pinel : réduction d'impôt et plafond de loyer (art. 199 novovicies du CGI)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

PLAFOND_PRIX_REVIENT = 30_000_000
PLAFOND_PAR_M2 = 550_000
DUREES_AUTORISEES = (6, 9, 12)


@dataclass(frozen=True)
class PeriodePinel:
    annee_debut: int
    annee_fin: int
    taux_annuel: Decimal


@dataclass(frozen=True)
class EngagementPinel:
    date_mise_en_location: date
    duree_annees: int
    prix_revient: int
    surface_habitable: Decimal
    periodes: tuple[PeriodePinel, ...]

    def __post_init__(self) -> None:
        if self.duree_annees not in DUREES_AUTORISEES:
            raise ValueError("La durée d'engagement Pinel doit être de 6, 9 ou 12 ans.")
        triees = sorted(self.periodes, key=lambda p: p.annee_debut)
        for p in triees:
            if p.annee_fin < p.annee_debut:
                raise ValueError(f"Période Pinel {p.annee_debut}-{p.annee_fin} invalide.")
        for avant, apres in zip(triees, triees[1:], strict=False):
            if apres.annee_debut <= avant.annee_fin:
                raise ValueError("Les périodes Pinel se chevauchent.")


def base_reduction(e: EngagementPinel) -> int:
    plafond_surface = int((PLAFOND_PAR_M2 * e.surface_habitable).to_integral_value(ROUND_HALF_UP))
    return min(e.prix_revient, PLAFOND_PRIX_REVIENT, plafond_surface)


def reduction_annee(e: EngagementPinel, annee: int) -> int:
    for p in e.periodes:
        if p.annee_debut <= annee <= p.annee_fin:
            return int((Decimal(base_reduction(e)) * p.taux_annuel / 100).quantize(Decimal(1), ROUND_DOWN))
    return 0


def reduction_cumulee(e: EngagementPinel, jusqu_a: int) -> int:
    debut = min((p.annee_debut for p in e.periodes), default=jusqu_a + 1)
    return sum(reduction_annee(e, a) for a in range(debut, jusqu_a + 1))


def reduction_totale(e: EngagementPinel) -> int:
    fin = max((p.annee_fin for p in e.periodes), default=0)
    return reduction_cumulee(e, fin)


def fin_engagement(e: EngagementPinel) -> date:
    debut = e.date_mise_en_location
    annee = debut.year + e.duree_annees
    try:
        anniversaire = debut.replace(year=annee)
    except ValueError:
        anniversaire = date(annee, 3, 1)
    return anniversaire - timedelta(days=1)


def plafond_loyer_mensuel(plafond_m2: int, surface_habitable: Decimal, surface_annexes: Decimal) -> int:
    """Plafond mensuel hors charges en centimes ; `plafond_m2` : centimes par m² (paramètre de zone)."""
    surface_utile = surface_habitable + min(surface_annexes / 2, Decimal(8))
    coefficient = min(Decimal("0.7") + Decimal(19) / surface_utile, Decimal("1.2"))
    coefficient = coefficient.quantize(Decimal("0.01"), ROUND_HALF_UP)
    return int((Decimal(plafond_m2) * coefficient * surface_utile).quantize(Decimal(1), ROUND_HALF_UP))
