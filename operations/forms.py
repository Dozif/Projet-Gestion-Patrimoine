from django import forms

from commun.forms import MontantField

from .models import Categorie, Operation


class CategorieChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.libelle_complet


class OperationForm(forms.ModelForm):
    categorie = CategorieChoiceField(queryset=Categorie.objects.filter(active=True), label="Catégorie")
    montant = MontantField(label="Montant (€)")

    class Meta:
        model = Operation
        fields = ["bien", "date_paiement", "categorie", "libelle", "montant", "justificatif", "commentaire"]
        widgets = {
            "date_paiement": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "commentaire": forms.Textarea(attrs={"rows": 2}),
        }
