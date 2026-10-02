from datetime import date

from django.http import Http404, HttpResponse
from django.shortcuts import render

from biens.models import Bien
from commun.annees import annee_demandee
from fiscalite.models import Configuration, ParametresAnnuels
from fiscalite.services import ParametresManquants, calculer_annee

from .presentation import ecrire_csv, estimation_impot
from .suivi import alerte_loyers, alertes_pinel, etat_loyers, resume_pinel


def _annees(aujourd_hui: date) -> list[int]:
    premiere = Configuration.charger().premiere_annee
    return list(range(aujourd_hui.year, min(premiere, aujourd_hui.year) - 1, -1))


def tableau_de_bord(request):
    aujourd_hui = date.today()
    annee = annee_demandee(request, aujourd_hui.year)
    contexte = {
        "annee": annee, "annees": _annees(aujourd_hui), "aujourd_hui": aujourd_hui, "annee_courante": aujourd_hui.year,
    }
    try:
        resultat, _ = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        return render(request, "declaration/tableau_de_bord.html", {**contexte, "erreur": str(erreur)})
    parametres = ParametresAnnuels.objects.get(annee=annee)
    biens = {b.pk: b for b in Bien.objects.select_related("pinel")}
    cartes, alertes, pinels = [], [], []
    for r in resultat.biens:
        bien = biens[r.bien_id]
        loyers = etat_loyers(bien, annee, aujourd_hui)
        cartes.append({
            "bien": bien, "recettes": r.recettes, "frais": r.frais, "interets": r.interets,
            "resultat": r.resultat, "loyers": loyers,
        })
        alerte = alerte_loyers(bien, loyers)
        if alerte:
            alertes.append(alerte)
        resume = resume_pinel(bien, annee, aujourd_hui, parametres.plafonds_pinel_m2)
        if resume:
            pinels.append(resume)
            alertes.extend(alertes_pinel(resume, aujourd_hui))
    alertes.extend({"niveau": "info", "titre": "Déficit foncier", "texte": texte} for texte in resultat.alertes)
    estimation = estimation_impot(
        resultat.deficit.revenu_net_estime, resultat.deficit.case_4bc, parametres.tmi,
        parametres.taux_prelevements_sociaux,
    )
    return render(request, "declaration/tableau_de_bord.html", {
        **contexte, "resultat": resultat, "parametres": parametres, "cartes": cartes, "alertes": alertes,
        "pinels": pinels, "estimation": estimation,
    })


def export_csv(request, annee):
    try:
        resultat, contexte = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        raise Http404(str(erreur)) from None
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="declaration-2044-{annee}.csv"'
    reponse.write("\ufeff")
    ecrire_csv(reponse, resultat, contexte)
    return reponse
