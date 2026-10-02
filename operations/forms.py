from django import forms

from commun.forms import MontantField

from .models import Categorie, Operation, ReleveAgence


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


class ReleveForm(forms.ModelForm):
    periode = forms.DateField(
        label="Mois concerné", input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )
    loyer_brut = MontantField(label="Loyer brut (€)")
    charges_recues = MontantField(label="Charges reçues du locataire (€)", required=False, minimum=0, valeur_si_vide=0)
    honoraires = MontantField(label="Honoraires retenus par l'agence (€)", required=False, minimum=0, valeur_si_vide=0)

    class Meta:
        model = ReleveAgence
        fields = ["bien", "periode", "date_versement", "loyer_brut", "charges_recues", "honoraires", "commentaire"]
        widgets = {
            "date_versement": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "commentaire": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        donnees = super().clean()
        recu = (donnees.get("loyer_brut") or 0) + (donnees.get("charges_recues") or 0)
        if (donnees.get("honoraires") or 0) > recu:
            raise forms.ValidationError("Les honoraires dépassent les sommes reçues du locataire.")
        return donnees
