"""Suivi de l'année : loyers mois par mois, engagement Pinel et alertes du tableau de bord."""

from datetime import date, timedelta

from commun.montants import format_euros
from fiscal.pinel import fin_engagement, plafond_loyer_mensuel, reduction_annee, reduction_cumulee, reduction_totale
from operations.models import NatureOperation, Operation

NOMS_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
LIBELLES_ETAT = {"encaisse": "encaissé", "manquant": "non saisi", "a_venir": "à venir", "sans_bail": "pas de bail"}


def _dernier_jour(annee: int, mois: int) -> date:
    return date(annee + mois // 12, mois % 12 + 1, 1) - timedelta(days=1)


def etat_loyers(bien, annee: int, aujourd_hui: date) -> list[dict]:
    encaisses = set(
        Operation.objects.filter(
            bien=bien, date_paiement__year=annee,
            categorie__nature=NatureOperation.RECETTE_IMPOSABLE, categorie__ligne_2044="211",
        ).values_list("date_paiement__month", flat=True)
    )
    etats = []
    for mois in range(1, 13):
        debut, fin = date(annee, mois, 1), _dernier_jour(annee, mois)
        if mois in encaisses:
            etat = "encaisse"
        elif fin >= aujourd_hui:
            etat = "a_venir"
        elif bien.bail_en_cours(debut) or bien.bail_en_cours(fin):
            etat = "manquant"
        else:
            etat = "sans_bail"
        nom = NOMS_MOIS[mois - 1]
        etats.append(
            {"mois": mois, "initiale": nom[0].upper(), "nom": nom, "etat": etat, "libelle": LIBELLES_ETAT[etat]}
        )
    return etats


def alerte_loyers(bien, etats: list[dict]) -> dict | None:
    manquants = [e["nom"] for e in etats if e["etat"] == "manquant"]
    if not manquants:
        return None
    return {
        "niveau": "attention",
        "titre": f"Loyer non saisi — {bien.nom}",
        "texte": f"Aucun loyer encaissé en {', '.join(manquants)}.",
    }


def resume_pinel(bien, annee: int, aujourd_hui: date, plafonds_m2: dict) -> dict | None:
    engagement = getattr(bien, "pinel", None)
    if engagement is None:
        return None
    e = engagement.vers_fiscal()
    total = reduction_totale(e)
    cumul = reduction_cumulee(e, annee)
    bail = bien.bail_en_cours(aujourd_hui)
    plafond_m2 = (plafonds_m2 or {}).get(engagement.zone)
    plafond = (
        plafond_loyer_mensuel(int(plafond_m2), bien.surface_habitable, bien.surface_annexes)
        if plafond_m2 and bail else None
    )
    return {
        "bien": bien,
        "zone": engagement.zone,
        "reduction_annee": reduction_annee(e, annee),
        "cumul": cumul,
        "total": total,
        "pourcentage": cumul * 100 // total if total else 0,
        "fin": fin_engagement(e),
        "loyer": bail.loyer_hc if bail else None,
        "plafond": plafond,
        "depasse": bool(plafond and bail.loyer_hc > plafond),
    }


def alertes_pinel(resume: dict, aujourd_hui: date) -> list[dict]:
    alertes = []
    nom = resume["bien"].nom
    if aujourd_hui <= resume["fin"] <= aujourd_hui + timedelta(days=365):
        alertes.append({
            "niveau": "info",
            "titre": f"Fin d'engagement Pinel le {resume['fin']:%d/%m/%Y} — {nom}",
            "texte": "Les contraintes du dispositif (plafonds de loyer et de ressources) prendront fin.",
        })
    if resume["depasse"]:
        alertes.append({
            "niveau": "attention",
            "titre": f"Loyer au-dessus du plafond Pinel — {nom}",
            "texte": f"Loyer {format_euros(resume['loyer'])} pour un plafond de {format_euros(resume['plafond'])}.",
        })
    return alertes
