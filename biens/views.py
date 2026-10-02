from datetime import date

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from fiscal.pinel import fin_engagement, reduction_annee, reduction_cumulee, reduction_totale

from .forms import BailForm, BienForm, EngagementPinelForm, LocataireForm, PeriodeFormSet, verifier_engagement
from .models import Bail, Bien, EngagementPinel, Locataire


def liste(request):
    return render(request, "biens/liste.html", {"biens": Bien.objects.all()})


def creer(request):
    return _formulaire_bien(request, Bien())


def modifier(request, pk):
    return _formulaire_bien(request, get_object_or_404(Bien, pk=pk))


def _formulaire_bien(request, bien):
    form = BienForm(request.POST or None, instance=bien)
    if request.method == "POST" and form.is_valid():
        bien = form.save()
        messages.success(request, f"Bien « {bien.nom} » enregistré.")
        return redirect(bien)
    titre = "Modifier le bien" if bien.pk else "Nouveau bien"
    return render(request, "commun/formulaire.html", {"form": form, "titre": titre, "retour": reverse("biens:liste")})


def detail(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    pinel = getattr(bien, "pinel", None)
    aujourd_hui = date.today()
    contexte = {
        "bien": bien,
        "bail": bien.bail_en_cours(aujourd_hui),
        "baux": bien.baux.select_related("locataire"),
        "pinel": pinel,
    }
    if pinel is not None:
        engagement = pinel.vers_fiscal()
        contexte.update(
            annee=aujourd_hui.year,
            reduction_annee=reduction_annee(engagement, aujourd_hui.year),
            reduction_cumulee=reduction_cumulee(engagement, aujourd_hui.year),
            reduction_totale=reduction_totale(engagement),
            fin_engagement=fin_engagement(engagement),
        )
    return render(request, "biens/detail.html", contexte)


def pinel(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    engagement = getattr(bien, "pinel", None) or EngagementPinel(bien=bien)
    form = EngagementPinelForm(request.POST or None, instance=engagement)
    formset = PeriodeFormSet(request.POST or None, instance=engagement, prefix="periodes")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        erreur = verifier_engagement(form, formset)
        if erreur:
            form.add_error(None, erreur)
        else:
            with transaction.atomic():
                engagement = form.save()
                formset.instance = engagement
                formset.save()
            messages.success(request, "Engagement Pinel enregistré.")
            return redirect(bien)
    return render(request, "biens/pinel.html", {"bien": bien, "form": form, "formset": formset})


def creer_bail(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    return _formulaire_bail(request, bien, Bail(bien=bien))


def modifier_bail(request, pk, bail_pk):
    bien = get_object_or_404(Bien, pk=pk)
    return _formulaire_bail(request, bien, get_object_or_404(Bail, pk=bail_pk, bien=bien))


def _formulaire_bail(request, bien, bail):
    locataire = bail.locataire if bail.pk else Locataire()
    form_locataire = LocataireForm(request.POST or None, instance=locataire, prefix="locataire")
    form_bail = BailForm(request.POST or None, instance=bail, prefix="bail")
    if request.method == "POST" and form_locataire.is_valid() and form_bail.is_valid():
        with transaction.atomic():
            bail = form_bail.save(commit=False)
            bail.bien = bien
            bail.locataire = form_locataire.save()
            bail.save()
        messages.success(request, "Bail enregistré.")
        return redirect(bien)
    return render(
        request, "biens/bail.html",
        {"bien": bien, "bail": bail, "form_locataire": form_locataire, "form_bail": form_bail},
    )
