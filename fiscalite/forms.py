from django import forms

from commun.forms import MontantField

from .models import Configuration, DecompteCopropriete, DeficitAnterieur


class DecompteForm(forms.ModelForm):
    part_non_deductible = MontantField(label="Part non déductible (€)", minimum=0)

    class Meta:
        model = DecompteCopropriete
        fields = ["bien", "annee", "part_non_deductible", "commentaire"]
        widgets = {"commentaire": forms.Textarea(attrs={"rows": 2})}


class DeficitForm(forms.ModelForm):
    montant = MontantField(label="Solde restant à imputer (€)")

    class Meta:
        model = DeficitAnterieur
        fields = ["annee_origine", "montant"]


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = Configuration
        fields = ["premiere_annee"]
