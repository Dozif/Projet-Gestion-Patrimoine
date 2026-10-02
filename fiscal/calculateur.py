"""Calculateurs par régime fiscal et registre des régimes pris en charge."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .calcul_2044 import ResultatBien, calculer_bien
from .deficit import DUREE_REPORT_ANS, ResultatDeficit, appliquer_deficits
from .modeles import Bien, DeficitReportable, Operation, ParametresAnnuels, en_euros

REGIME_FONCIER_REEL = "FONCIER_REEL"


@dataclass(frozen=True)
class ResultatFoncier:
    annee: int
    biens: tuple[ResultatBien, ...]
    total_recettes: int
    total_frais: int
    total_interets: int
    resultat_global: int
    deficit: ResultatDeficit
    alertes: tuple[str, ...]


class Calculateur(Protocol):
    regime: str

    def calculer(
        self,
        annee: int,
        biens: Iterable[Bien],
        operations: Iterable[Operation],
        deficits: Iterable[DeficitReportable],
        params: ParametresAnnuels,
    ) -> ResultatFoncier: ...


class CalculateurFoncierReel:
    regime = REGIME_FONCIER_REEL

    def calculer(
        self,
        annee: int,
        biens: Iterable[Bien],
        operations: Iterable[Operation],
        deficits: Iterable[DeficitReportable],
        params: ParametresAnnuels,
    ) -> ResultatFoncier:
        if params.annee != annee:
            raise ValueError(f"Paramètres de l'année {params.annee} fournis pour un calcul {annee}.")
        operations = list(operations)
        resultats = tuple(
            calculer_bien(annee, b, operations, params) for b in biens if b.regime == self.regime
        )
        recettes = sum(r.recettes for r in resultats)
        frais = sum(r.frais for r in resultats)
        interets = sum(r.interets for r in resultats)
        deficit = appliquer_deficits(annee, recettes, frais, interets, deficits, params)

        alertes: list[str] = []
        if deficit.case_4bc > 0:
            alertes.append(
                f"Déficit imputé sur le revenu global en {annee} : les biens doivent rester loués "
                f"jusqu'au 31/12/{annee + 3}."
            )
        for d in deficit.deficits_apres:
            if d.annee_origine == annee - DUREE_REPORT_ANS:
                alertes.append(
                    f"Déficit {d.annee_origine} : dernière année d'imputation, "
                    f"{en_euros(d.montant)} € seront perdus après {annee}."
                )
        for d in deficit.deficits_expires:
            alertes.append(f"Déficit {d.annee_origine} expiré : {en_euros(d.montant)} € non imputés.")

        return ResultatFoncier(
            annee, resultats, recettes, frais, interets, recettes - frais - interets, deficit, tuple(alertes)
        )


_CALCULATEURS: dict[str, Calculateur] = {REGIME_FONCIER_REEL: CalculateurFoncierReel()}


def calculateur_pour(regime: str) -> Calculateur:
    try:
        return _CALCULATEURS[regime]
    except KeyError:
        raise NotImplementedError(f"Régime fiscal non pris en charge : {regime}") from None
