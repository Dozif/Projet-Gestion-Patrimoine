from django import forms

from commun.forms import MontantField

from .import_csv import Colonnes
from .models import Pret


class PretForm(forms.ModelForm):
    capital_emprunte = MontantField(label="Capital emprunté (€)")

    class Meta:
        model = Pret
        fields = ["bien", "banque", "libelle", "capital_emprunte", "date_debut"]
        widgets = {"date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


def _deviner(entetes, *mots):
    for entete in entetes:
        if any(mot in entete.lower() for mot in mots):
            return entete
    return None


class ColonnesForm(forms.Form):
    def __init__(self, entetes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choix = [(e, e) for e in entetes]
        self.fields["date"] = forms.ChoiceField(
            label="Colonne de la date", choices=choix, initial=_deviner(entetes, "date", "échéance")
        )
        self.fields["capital"] = forms.ChoiceField(
            label="Colonne du capital remboursé", choices=choix, initial=_deviner(entetes, "capital", "amorti")
        )
        self.fields["interets"] = forms.ChoiceField(
            label="Colonne des intérêts", choices=choix, initial=_deviner(entetes, "intér", "interet")
        )
        self.fields["assurance"] = forms.ChoiceField(
            label="Colonne de l'assurance emprunteur", choices=[("", "— aucune —"), *choix], required=False,
            initial=_deviner(entetes, "assur"),
        )

    def colonnes(self) -> Colonnes:
        return Colonnes(**self.cleaned_data)
