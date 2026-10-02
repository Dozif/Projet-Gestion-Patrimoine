from datetime import date

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from biens.models import Bien
from commun.annees import annee_demandee
from fiscal.pinel import reduction_annee
from fiscalite.models import Configuration, ParametresAnnuels
from fiscalite.services import ParametresManquants, calculer_annee

from .models import DeclarationFigee
from .presentation import (
    cases_2042,
    colonnes_biens,
    detail_ligne,
    ecrire_csv,
    empreinte,
    estimation_impot,
    lignes_declaration,
    resultat_vers_dict,
)
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


def declaration(request):
    aujourd_hui = date.today()
    annee = annee_demandee(request, aujourd_hui.year - 1)
    contexte = {"annee": annee, "annees": _annees(aujourd_hui)}
    try:
        resultat, contexte_fiscal = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        return render(request, "declaration/declaration.html", {**contexte, "erreur": str(erreur)})
    ligne_choisie = request.GET.get("ligne", "")
    pinel = [
        {"bien": bien.nom, "reduction": reduction_annee(bien.pinel.vers_fiscal(), annee)}
        for bien in Bien.objects.filter(pinel__isnull=False).select_related("pinel")
    ]
    contexte.update(
        resultat=resultat,
        colonnes=colonnes_biens(resultat, contexte_fiscal),
        lignes=lignes_declaration(resultat),
        ligne_choisie=ligne_choisie,
        detail=detail_ligne(resultat, contexte_fiscal, ligne_choisie),
        cases=cases_2042(resultat),
        pinel=[p for p in pinel if p["reduction"]],
    )
    figee = DeclarationFigee.objects.filter(annee=annee).first()
    actuelle = empreinte(resultat_vers_dict(resultat, contexte_fiscal))
    contexte.update(figee=figee, modifiee=bool(figee and figee.empreinte != actuelle))
    return render(request, "declaration/declaration.html", contexte)


@require_POST
def figer(request, annee):
    try:
        resultat, contexte_fiscal = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        raise Http404(str(erreur)) from None
    donnees = resultat_vers_dict(resultat, contexte_fiscal)
    DeclarationFigee.objects.update_or_create(
        annee=annee, defaults={"donnees": donnees, "empreinte": empreinte(donnees)}
    )
    messages.success(request, f"Déclaration {annee} figée : elle sert de référence pour ce qui a été déclaré.")
    return redirect(f"{reverse('declaration:declaration')}?annee={annee}")


@require_POST
def defiger(request, annee):
    DeclarationFigee.objects.filter(annee=annee).delete()
    messages.success(request, f"Déclaration {annee} défigée.")
    return redirect(f"{reverse('declaration:declaration')}?annee={annee}")


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
