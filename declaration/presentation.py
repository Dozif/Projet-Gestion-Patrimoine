"""Mise en forme des résultats du moteur fiscal pour les écrans et les exports."""

from __future__ import annotations

import csv
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from fiscal import en_euros
from fiscal.calcul_2044 import LIGNES

ORDRE = ("211", "212", "213", "214", "215", "221", "222", "223", "224", "225", "226", "227", "229", "230", "240", "250")
TOUJOURS = frozenset({"211", "215", "240", "250"})
TOTAUX = frozenset({"215", "240"})
CASES = (
    ("4BA", "Revenu foncier imposable", "case_4ba"),
    ("4BB", "Déficit imputable sur les revenus fonciers", "case_4bb"),
    ("4BC", "Déficit imputable sur le revenu global", "case_4bc"),
    ("4BD", "Déficits antérieurs non encore imputés", "case_4bd"),
)


RECETTES = ("211", "212", "213", "214")
FRAIS = ("221", "222", "223", "224", "225", "226", "227", "229")


def biens_actifs(resultat) -> list:
    """Biens ayant au moins un montant dans l'année (un bien acheté plus tard n'apparaît pas)."""
    return [b for b in resultat.biens if b.resultat or any(ligne.montant for ligne in b.lignes.values())]


def colonnes_biens(resultat, contexte) -> list[str]:
    noms = {b.id: b.nom for b in contexte.biens}
    return [noms[r.bien_id] for r in biens_actifs(resultat)]


def _montants_arrondis(bien) -> dict:
    """Lignes saisies arrondies à l'euro, totaux recalculés à partir de ces arrondis (comme sur la 2044)."""
    m = {code: en_euros(bien.lignes[code].montant) * 100 for code in ORDRE if code not in TOTAUX}
    m["215"] = sum(m[c] for c in RECETTES)
    m["240"] = sum(m[c] for c in FRAIS) - m["230"]
    m["resultat"] = m["215"] - m["240"] - m["250"]
    return m


def lignes_declaration(resultat) -> list[dict]:
    par_bien = [_montants_arrondis(b) for b in biens_actifs(resultat)]
    lignes = []
    for code in ORDRE:
        valeurs = [m[code] for m in par_bien]
        if code == "230":
            valeurs = [-v for v in valeurs]
        if code not in TOUJOURS and not any(valeurs):
            continue
        lignes.append({
            "code": code, "libelle": LIGNES[code][0], "valeurs": valeurs, "total": sum(valeurs),
            "type": "total" if code in TOTAUX else "ligne",
        })
    valeurs = [m["resultat"] for m in par_bien]
    lignes.append(
        {"code": "", "libelle": "Résultat foncier", "valeurs": valeurs, "total": sum(valeurs), "type": "resultat"}
    )
    return lignes


def detail_ligne(resultat, contexte, code: str) -> dict | None:
    if code not in ORDRE:
        return None
    montants = {o.id: o.montant for o in contexte.operations}
    operations = [
        {"texte": contexte.sources.get(i, f"Opération {i}"), "montant": montants[i]}
        for r in resultat.biens
        for i in r.lignes[code].explication.operation_ids
    ]
    libelle, regle, source = LIGNES[code]
    total = sum(r.lignes[code].montant for r in resultat.biens)
    return {
        "code": code, "libelle": libelle, "regle": regle, "source": source, "operations": operations, "total": total
    }


def cases_2042(resultat) -> list[dict]:
    return [
        {"code": code, "libelle": libelle, "montant": getattr(resultat.deficit, attribut)}
        for code, libelle, attribut in CASES
    ]


def _arrondi(valeur: Decimal) -> int:
    return int(valeur.quantize(Decimal(1), ROUND_HALF_UP))


def estimation_impot(revenu_net: int, deficit_global: int, tmi: Decimal, taux_ps: Decimal) -> dict:
    """Impôt + prélèvements sociaux sur le revenu foncier net, économie d'impôt due au déficit (centimes)."""
    return {
        "impot": _arrondi(Decimal(revenu_net) * (tmi + taux_ps) / 100),
        "economie": _arrondi(Decimal(deficit_global) * tmi / 100),
    }


def resultat_vers_dict(resultat, contexte) -> dict:
    return {
        "annee": resultat.annee,
        "biens": {
            str(bien.bien_id): {
                "lignes": {code: bien.lignes[code].montant for code in ORDRE}, "resultat": bien.resultat
            }
            for bien in biens_actifs(resultat)
        },
        "cases": {c["code"]: c["montant"] for c in cases_2042(resultat)},
        "deficits_apres": [[d.annee_origine, d.montant] for d in resultat.deficit.deficits_apres],
    }


def empreinte(donnees: dict) -> str:
    return hashlib.sha256(json.dumps(donnees, sort_keys=True).encode()).hexdigest()


def _texte_csv(valeur: str) -> str:
    """Neutralise une cellule qu'un tableur prendrait pour une formule (=, +, -, @…)."""
    return "'" + valeur if valeur[:1] in ("=", "+", "-", "@", "\t", "\r") else valeur


def ecrire_csv(fichier, resultat, contexte) -> None:
    ecrivain = csv.writer(fichier, delimiter=";")
    noms = [_texte_csv(nom) for nom in colonnes_biens(resultat, contexte)]
    ecrivain.writerow(["Ligne", "Libellé", *noms, "Total"])
    for ligne in lignes_declaration(resultat):
        ecrivain.writerow(
            [ligne["code"], ligne["libelle"], *(en_euros(v) for v in ligne["valeurs"]), en_euros(ligne["total"])]
        )
    ecrivain.writerow([])
    ecrivain.writerow(["Case", "Libellé", "Montant"])
    for case in cases_2042(resultat):
        ecrivain.writerow([case["code"], case["libelle"], en_euros(case["montant"])])
