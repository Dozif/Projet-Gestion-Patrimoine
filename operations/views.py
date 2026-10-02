from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from biens.models import Bien

from .forms import OperationForm
from .models import NatureOperation, Operation

FILTRES_NATURE = {
    "recettes": [NatureOperation.RECETTE_IMPOSABLE, NatureOperation.RECETTE_NON_IMPOSABLE],
    "deductibles": [NatureOperation.CHARGE_DEDUCTIBLE, NatureOperation.INTERETS],
    "non-deductibles": [NatureOperation.CHARGE_NON_DEDUCTIBLE],
}
PUCES = (
    ("", "Toutes"), ("recettes", "Recettes"), ("deductibles", "Déductibles"), ("non-deductibles", "Non déductibles")
)


def _requete(params):
    return "?" + urlencode({k: v for k, v in params.items() if v not in ("", None)})


def liste(request):
    annees = sorted({d.year for d in Operation.objects.dates("date_paiement", "year")}, reverse=True)
    try:
        annee = int(request.GET.get("annee") or (annees[0] if annees else date.today().year))
    except ValueError:
        annee = date.today().year
    if annee not in annees:
        annees = sorted({*annees, annee}, reverse=True)
    requete = Operation.objects.filter(date_paiement__year=annee).select_related("bien", "categorie")
    bien_id = request.GET.get("bien", "")
    bien_id = int(bien_id) if bien_id.isdigit() else None
    if bien_id:
        requete = requete.filter(bien_id=bien_id)
    nature = request.GET.get("nature", "")
    if nature in FILTRES_NATURE:
        requete = requete.filter(categorie__nature__in=FILTRES_NATURE[nature])
    else:
        nature = ""
    operations = list(requete)
    totaux = {
        "recettes": sum(o.montant for o in operations if o.categorie.nature == NatureOperation.RECETTE_IMPOSABLE),
        "deductibles": sum(o.montant for o in operations if o.categorie.nature in FILTRES_NATURE["deductibles"]),
        "non_deductibles": sum(
            o.montant for o in operations if o.categorie.nature == NatureOperation.CHARGE_NON_DEDUCTIBLE
        ),
    }
    base = {"annee": annee, "bien": bien_id}
    puces = [
        {"libelle": libelle, "url": _requete({**base, "nature": code}), "actif": code == nature}
        for code, libelle in PUCES
    ]
    return render(request, "operations/liste.html", {
        "operations": operations, "annee": annee, "annees": annees, "biens": Bien.objects.all(),
        "bien_id": bien_id, "nature": nature, "puces": puces, "totaux": totaux,
    })


def creer(request):
    initial = {"date_paiement": date.today(), "bien": request.GET.get("bien")}
    return _formulaire(request, Operation(), initial)


def modifier(request, pk):
    return _formulaire(request, get_object_or_404(Operation, pk=pk), None)


def _formulaire(request, operation, initial):
    form = OperationForm(request.POST or None, request.FILES or None, instance=operation, initial=initial)
    if request.method == "POST" and form.is_valid():
        operation = form.save()
        messages.success(request, f"Opération « {operation.libelle} » enregistrée.")
        return redirect(f"{reverse('operations:liste')}?annee={operation.date_paiement.year}")
    contexte = {
        "form": form,
        "titre": "Modifier l'opération" if operation.pk else "Nouvelle opération",
        "retour": reverse("operations:liste"),
    }
    if operation.pk:
        contexte["suppression"] = reverse("operations:supprimer", args=[operation.pk])
    return render(request, "commun/formulaire.html", contexte)


@require_POST
def supprimer(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    annee = operation.date_paiement.year
    operation.delete()
    messages.success(request, "Opération supprimée.")
    return redirect(f"{reverse('operations:liste')}?annee={annee}")


def justificatif(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    if not operation.justificatif:
        raise Http404("Aucun justificatif.")
    return FileResponse(operation.justificatif.open("rb"), filename=Path(operation.justificatif.name).name)
