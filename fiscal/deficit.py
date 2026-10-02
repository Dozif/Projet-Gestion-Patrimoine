"""Imputation des déficits fonciers (art. 156-I-3° du CGI)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .modeles import DeficitReportable, ParametresAnnuels

DUREE_REPORT_ANS = 10


@dataclass(frozen=True)
class ResultatDeficit:
    case_4ba: int
    case_4bb: int
    case_4bc: int
    case_4bd: int
    imputations: tuple[DeficitReportable, ...]
    deficits_apres: tuple[DeficitReportable, ...]
    deficits_expires: tuple[DeficitReportable, ...]
    revenu_net_estime: int


def appliquer_deficits(
    annee: int,
    recettes: int,
    frais: int,
    interets: int,
    deficits_anterieurs: Iterable[DeficitReportable],
    params: ParametresAnnuels,
) -> ResultatDeficit:
    stock = sorted((d for d in deficits_anterieurs if d.montant > 0), key=lambda d: d.annee_origine)
    if any(d.annee_origine >= annee for d in stock):
        raise ValueError(f"Un déficit reporté doit être antérieur à {annee}.")
    expires = tuple(d for d in stock if d.annee_origine < annee - DUREE_REPORT_ANS)
    valides = tuple(d for d in stock if d.annee_origine >= annee - DUREE_REPORT_ANS)
    case_4bd = sum(d.montant for d in valides)

    resultat = recettes - frais - interets
    if resultat >= 0:
        reste = resultat
        imputations: list[DeficitReportable] = []
        apres: list[DeficitReportable] = []
        for d in valides:
            impute = min(d.montant, reste)
            reste -= impute
            if impute:
                imputations.append(DeficitReportable(d.annee_origine, impute))
            if d.montant - impute:
                apres.append(DeficitReportable(d.annee_origine, d.montant - impute))
        return ResultatDeficit(resultat, 0, 0, case_4bd, tuple(imputations), tuple(apres), expires, reste)

    deficit = -resultat
    part_interets = min(max(0, interets - recettes), deficit)
    part_autres = deficit - part_interets
    imputable_global = min(part_autres, params.plafond_imputation_revenu_global)
    reportable = deficit - imputable_global
    apres = valides + ((DeficitReportable(annee, reportable),) if reportable else ())
    return ResultatDeficit(0, reportable, imputable_global, case_4bd, (), apres, expires, 0)
