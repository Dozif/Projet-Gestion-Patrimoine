from collections import defaultdict

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ColonnesForm, EcheanceForm, PretForm
from .import_csv import ErreurImport, decoder, lire_echeancier, lire_entetes
from .models import Echeance, Pret

TAILLE_MAX_CSV = 1_000_000


def liste(request):
    return render(request, "credit/liste.html", {"prets": Pret.objects.select_related("bien")})


def creer(request):
    return _formulaire(request, Pret())


def modifier(request, pk):
    return _formulaire(request, get_object_or_404(Pret, pk=pk))


def _formulaire(request, pret):
    form = PretForm(request.POST or None, instance=pret)
    if request.method == "POST" and form.is_valid():
        pret = form.save()
        messages.success(request, "Prêt enregistré.")
        return redirect(pret)
    titre = "Modifier le prêt" if pret.pk else "Nouveau prêt"
    return render(request, "commun/formulaire.html", {"form": form, "titre": titre, "retour": reverse("credit:liste")})


def detail(request, pk):
    pret = get_object_or_404(Pret.objects.select_related("bien"), pk=pk)
    echeances = list(pret.echeances.all())
    par_annee = defaultdict(lambda: {"capital": 0, "interets": 0, "assurance": 0, "frais": 0, "deductible": 0})
    for e in echeances:
        total = par_annee[e.date.year]
        total["capital"] += e.capital
        total["interets"] += e.interets
        total["assurance"] += e.assurance
        total["frais"] += e.frais
        total["deductible"] += e.deductible
    annees = [{"annee": a, **t} for a, t in sorted(par_annee.items(), reverse=True)]
    return render(request, "credit/detail.html", {"pret": pret, "echeances": echeances, "annees": annees})


def importer(request, pk):
    pret = get_object_or_404(Pret, pk=pk)
    cle = f"import_echeancier_{pk}"
    if request.method == "POST" and "recommencer" in request.POST:
        request.session.pop(cle, None)
        return redirect("credit:importer", pk=pk)
    if request.method == "POST" and "fichier" in request.FILES:
        fichier = request.FILES["fichier"]
        if fichier.size > TAILLE_MAX_CSV:
            messages.error(request, "Le fichier dépasse 1 Mo.")
            return redirect("credit:importer", pk=pk)
        try:
            texte = decoder(fichier.read())
            lire_entetes(texte)
        except ErreurImport as erreur:
            messages.error(request, str(erreur))
            return redirect("credit:importer", pk=pk)
        request.session[cle] = texte
        return redirect("credit:importer", pk=pk)
    texte = request.session.get(cle)
    if texte is None:
        return render(request, "credit/import_fichier.html", {"pret": pret})
    form = ColonnesForm(lire_entetes(texte), request.POST or None)
    apercu = None
    if request.method == "POST" and form.is_valid():
        try:
            lues = lire_echeancier(texte, form.colonnes())
        except ErreurImport as erreur:
            form.add_error(None, str(erreur))
        else:
            if "importer" in request.POST:
                with transaction.atomic():
                    for e in lues:
                        Echeance.objects.update_or_create(
                            pret=pret, date=e.date,
                            defaults={"capital": e.capital, "interets": e.interets, "assurance": e.assurance},
                        )
                del request.session[cle]
                messages.success(request, f"{len(lues)} échéances importées.")
                return redirect(pret)
            apercu = {
                "lignes": lues[:12], "nombre": len(lues),
                "capital": sum(e.capital for e in lues), "interets": sum(e.interets for e in lues),
                "assurance": sum(e.assurance for e in lues),
            }
    return render(request, "credit/import_colonnes.html", {"pret": pret, "form": form, "apercu": apercu})


def ajouter_echeance(request, pk):
    pret = get_object_or_404(Pret, pk=pk)
    return _formulaire_echeance(request, pret, Echeance(pret=pret))


def modifier_echeance(request, pk, echeance_pk):
    pret = get_object_or_404(Pret, pk=pk)
    return _formulaire_echeance(request, pret, get_object_or_404(Echeance, pk=echeance_pk, pret=pret))


def _formulaire_echeance(request, pret, echeance):
    form = EcheanceForm(request.POST or None, instance=echeance, pret=pret)
    if request.method == "POST" and form.is_valid():
        echeance = form.save(commit=False)
        echeance.pret = pret
        echeance.save()
        messages.success(request, f"Échéance du {echeance.date:%d/%m/%Y} enregistrée.")
        return redirect(pret)
    contexte = {
        "form": form, "titre": "Modifier l'échéance" if echeance.pk else "Nouvelle échéance",
        "intro": str(pret), "retour": pret.get_absolute_url(),
    }
    if echeance.pk:
        contexte["suppression"] = reverse("credit:supprimer_echeance", args=[pret.pk, echeance.pk])
    return render(request, "commun/formulaire.html", contexte)


@require_POST
def supprimer_echeance(request, pk, echeance_pk):
    pret = get_object_or_404(Pret, pk=pk)
    get_object_or_404(Echeance, pk=echeance_pk, pret=pret).delete()
    messages.success(request, "Échéance supprimée.")
    return redirect(pret)
