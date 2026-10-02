"""Conversion des données de la base vers le moteur `fiscal`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import count

import fiscal
from biens.models import Bien
from credit.models import Echeance
from operations.models import Operation

from .models import Configuration, DecompteCopropriete, DeficitAnterieur, ParametresAnnuels

ID_SYNTHETIQUE = 10**12


class ParametresManquants(Exception):
    pass


@dataclass(frozen=True)
class ContexteFiscal:
    annee: int
    biens: tuple[fiscal.Bien, ...]
    operations: tuple[fiscal.Operation, ...]
    params: fiscal.ParametresAnnuels
    sources: dict[int, str]


def contexte_fiscal(annee: int) -> ContexteFiscal:
    parametres = ParametresAnnuels.objects.filter(annee=annee).first()
    if parametres is None:
        raise ParametresManquants(
            f"Paramètres fiscaux {annee} absents : créez-les dans Paramètres avant de lancer le calcul."
        )
    operations: list[fiscal.Operation] = []
    sources: dict[int, str] = {}
    for o in Operation.objects.filter(date_paiement__year=annee).select_related("bien", "categorie"):
        operations.append(o.vers_fiscal())
        sources[o.pk] = f"{o.date_paiement:%d/%m/%Y} — {o.bien.nom} — {o.libelle}"

    identifiants = count(ID_SYNTHETIQUE)
    for e in Echeance.objects.filter(date__year=annee).select_related("pret__bien"):
        if e.deductible <= 0:
            continue
        i = next(identifiants)
        operations.append(fiscal.Operation(
            id=i, bien_id=e.pret.bien_id, date_paiement=e.date, montant=e.deductible,
            nature=fiscal.Nature.INTERETS, ligne_2044="250", libelle=f"Échéance du {e.date:%d/%m/%Y}",
        ))
        sources[i] = f"{e.date:%d/%m/%Y} — {e.pret.bien.nom} — échéance {e.pret.banque} (intérêts et assurance)"
    for d in DecompteCopropriete.objects.filter(annee=annee - 1, part_non_deductible__gt=0).select_related("bien"):
        i = next(identifiants)
        operations.append(fiscal.Operation(
            id=i, bien_id=d.bien_id, date_paiement=date(annee, 1, 1), montant=d.part_non_deductible,
            nature=fiscal.Nature.CHARGE_DEDUCTIBLE, ligne_2044="230", libelle=f"Régularisation copropriété {d.annee}",
        ))
        sources[i] = f"{d.bien.nom} — décompte {d.annee} du syndic (part non déductible)"

    return ContexteFiscal(
        annee=annee,
        biens=tuple(b.vers_fiscal() for b in Bien.objects.all()),
        operations=tuple(operations),
        params=parametres.vers_fiscal(),
        sources=sources,
    )


def _calculer(annee: int, deficits) -> tuple[fiscal.ResultatFoncier, ContexteFiscal]:
    contexte = contexte_fiscal(annee)
    calculateur = fiscal.calculateur_pour(fiscal.REGIME_FONCIER_REEL)
    resultat = calculateur.calculer(annee, contexte.biens, contexte.operations, deficits, contexte.params)
    return resultat, contexte


def deficits_au_debut_de(annee: int) -> tuple[fiscal.DeficitReportable, ...]:
    premiere = Configuration.charger().premiere_annee
    if annee < premiere:
        raise ValueError(f"{annee} est antérieure à la première année gérée ({premiere}).")
    stock = tuple(fiscal.DeficitReportable(d.annee_origine, d.montant) for d in DeficitAnterieur.objects.all())
    for a in range(premiere, annee):
        stock = _calculer(a, stock)[0].deficit.deficits_apres
    return stock


def calculer_annee(annee: int) -> tuple[fiscal.ResultatFoncier, ContexteFiscal]:
    return _calculer(annee, deficits_au_debut_de(annee))
