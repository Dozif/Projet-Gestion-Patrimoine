from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ConfigurationForm, DecompteForm, DeficitForm
from .models import Configuration, DecompteCopropriete, DeficitAnterieur


def copropriete(request):
    form = DecompteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Décompte enregistré.")
        return redirect("fiscalite:copropriete")
    decomptes = DecompteCopropriete.objects.select_related("bien")
    return render(request, "fiscalite/copropriete.html", {"form": form, "decomptes": decomptes})


def modifier_decompte(request, pk):
    decompte = get_object_or_404(DecompteCopropriete, pk=pk)
    form = DecompteForm(request.POST or None, instance=decompte)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Décompte enregistré.")
        return redirect("fiscalite:copropriete")
    return render(request, "commun/formulaire.html", {
        "form": form, "titre": "Modifier le décompte", "retour": reverse("fiscalite:copropriete"),
        "suppression": reverse("fiscalite:supprimer_decompte", args=[pk]),
    })


@require_POST
def supprimer_decompte(request, pk):
    get_object_or_404(DecompteCopropriete, pk=pk).delete()
    messages.success(request, "Décompte supprimé.")
    return redirect("fiscalite:copropriete")


def deficits(request):
    configuration = Configuration.charger()
    form_config = ConfigurationForm(
        request.POST if "configuration" in request.POST else None, instance=configuration, prefix="config"
    )
    form_deficit = DeficitForm(request.POST if "deficit" in request.POST else None, prefix="deficit")
    if request.method == "POST":
        if "configuration" in request.POST and form_config.is_valid():
            form_config.save()
            messages.success(request, "Première année gérée enregistrée.")
            return redirect("fiscalite:deficits")
        if "deficit" in request.POST and form_deficit.is_valid():
            form_deficit.save()
            messages.success(request, "Déficit enregistré.")
            return redirect("fiscalite:deficits")
    return render(request, "fiscalite/deficits.html", {
        "configuration": configuration, "form_config": form_config, "form_deficit": form_deficit,
        "deficits": DeficitAnterieur.objects.all(),
    })


@require_POST
def supprimer_deficit(request, pk):
    get_object_or_404(DeficitAnterieur, pk=pk).delete()
    messages.success(request, "Déficit supprimé.")
    return redirect("fiscalite:deficits")
