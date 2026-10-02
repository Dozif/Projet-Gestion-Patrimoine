from django import forms
from django.forms import inlineformset_factory

import fiscal
from commun.forms import MontantField

from .models import Bail, Bien, EngagementPinel, Locataire, PeriodePinel

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class BienForm(forms.ModelForm):
    prix_revient = MontantField(label="Prix de revient (€)", help_text="Prix d'achat et frais d'acquisition.")

    class Meta:
        model = Bien
        fields = [
            "nom", "adresse", "surface_habitable", "surface_annexes", "date_acquisition", "prix_revient",
            "regime", "nb_locaux", "actif",
        ]
        widgets = {"date_acquisition": DATE, "adresse": forms.Textarea(attrs={"rows": 2})}


class EngagementPinelForm(forms.ModelForm):
    prix_revient = MontantField(label="Prix de revient retenu (€)")

    class Meta:
        model = EngagementPinel
        fields = ["date_mise_en_location", "duree_annees", "zone", "prix_revient", "surface_habitable"]
        widgets = {"date_mise_en_location": DATE}


PeriodeFormSet = inlineformset_factory(
    EngagementPinel, PeriodePinel, fields=["annee_debut", "annee_fin", "taux_annuel"], extra=2, can_delete=True,
    widgets={
        "annee_debut": forms.NumberInput(attrs={"aria-label": "Année de début"}),
        "annee_fin": forms.NumberInput(attrs={"aria-label": "Année de fin"}),
        "taux_annuel": forms.NumberInput(attrs={"aria-label": "Taux annuel en %", "step": "0.01"}),
    },
)


def verifier_engagement(form, formset) -> str | None:
    """Contrôle la cohérence du calendrier avec le moteur fiscal ; renvoie le message d'erreur éventuel."""
    periodes = tuple(
        fiscal.PeriodePinel(
            f.cleaned_data["annee_debut"], f.cleaned_data["annee_fin"], f.cleaned_data["taux_annuel"]
        )
        for f in formset.forms
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    )
    d = form.cleaned_data
    try:
        fiscal.EngagementPinel(
            d["date_mise_en_location"], d["duree_annees"], d["prix_revient"], d["surface_habitable"], periodes
        )
    except ValueError as erreur:
        return str(erreur)
    return None


class LocataireForm(forms.ModelForm):
    revenu_fiscal_reference = MontantField(label="Revenu fiscal de référence à la signature (€)", required=False)

    class Meta:
        model = Locataire
        fields = ["nom", "email", "telephone", "revenu_fiscal_reference", "nb_personnes_foyer"]


class BailForm(forms.ModelForm):
    loyer_hc = MontantField(label="Loyer mensuel hors charges (€)")
    provision_charges = MontantField(
        label="Provision mensuelle sur charges (€)", required=False, minimum=0, valeur_si_vide=0
    )
    depot_garantie = MontantField(label="Dépôt de garantie (€)", required=False, minimum=0, valeur_si_vide=0)

    class Meta:
        model = Bail
        fields = ["date_debut", "date_fin", "loyer_hc", "provision_charges", "depot_garantie"]
        widgets = {"date_debut": DATE, "date_fin": DATE}
