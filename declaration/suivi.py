"""Suivi de l'année : loyers mois par mois, engagement Pinel et alertes du tableau de bord."""

from datetime import date, timedelta

from django.db.models import Q

from commun.montants import format_euros
from fiscal.pinel import fin_engagement, plafond_loyer_mensuel, reduction_annee, reduction_cumulee, reduction_totale
from operations.models import NatureOperation, Operation

NOMS_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
LIBELLES_ETAT = {"encaisse": "encaissé", "manquant": "non saisi", "a_venir": "à venir", "sans_bail": "pas de bail"}


def plafond_m2_valide(valeur) -> bool:
    """Un plafond Pinel se saisit en centimes par m² : entier strictement positif."""
    return isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0


def _dernier_jour(annee: int, mois: int) -> date:
    return date(annee + mois // 12, mois % 12 + 1, 1) - timedelta(days=1)


def etat_loyers(bien, annee: int, aujourd_hui: date) -> list[dict]:
    # Un loyer versé par l'agence compte pour le mois de son relevé, même s'il est versé le mois suivant.
    loyers = Operation.objects.filter(
        Q(releve__isnull=True, date_paiement__year=annee) | Q(releve__periode__year=annee),
        bien=bien, categorie__nature=NatureOperation.RECETTE_IMPOSABLE, categorie__ligne_2044="211",
    ).select_related("releve")
    encaisses = {(o.releve.periode if o.releve_id else o.date_paiement).month for o in loyers}
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
    plafond_m2 = plafonds_m2.get(engagement.zone) if isinstance(plafonds_m2, dict) else None
    plafond_invalide = plafond_m2 is not None and not plafond_m2_valide(plafond_m2)
    plafond = (
        plafond_loyer_mensuel(plafond_m2, bien.surface_habitable, bien.surface_annexes)
        if plafond_m2 is not None and not plafond_invalide and bail else None
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
        "plafond_invalide": plafond_invalide,
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
