"""Moteur fiscal des revenus fonciers (sans dépendance externe)."""

from .calcul_2044 import ResultatBien, calculer_bien
from .calculateur import REGIME_FONCIER_REEL, CalculateurFoncierReel, ResultatFoncier, calculateur_pour
from .deficit import ResultatDeficit, appliquer_deficits
from .modeles import (
    Bien,
    DeficitReportable,
    Explication,
    LigneCalculee,
    Nature,
    Operation,
    ParametresAnnuels,
    en_euros,
)
from .pinel import (
    EngagementPinel,
    PeriodePinel,
    base_reduction,
    fin_engagement,
    plafond_loyer_mensuel,
    reduction_annee,
    reduction_cumulee,
    reduction_totale,
)

__all__ = [
    "EngagementPinel", "PeriodePinel", "base_reduction", "fin_engagement", "plafond_loyer_mensuel",
    "reduction_annee", "reduction_cumulee", "reduction_totale",
    "REGIME_FONCIER_REEL", "Bien", "CalculateurFoncierReel", "DeficitReportable", "Explication",
    "LigneCalculee", "Nature", "Operation", "ParametresAnnuels", "ResultatBien", "ResultatDeficit",
    "ResultatFoncier", "appliquer_deficits", "calculateur_pour", "calculer_bien", "en_euros",
]
