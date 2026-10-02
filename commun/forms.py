from django import forms

from .montants import centimes_vers_saisie, format_euros, parse_euros


class MontantField(forms.CharField):
    """Champ de saisie en euros ; `cleaned_data` contient des centimes."""

    def __init__(self, *, minimum: int | None = 1, valeur_si_vide=None, **kwargs):
        self.minimum = minimum
        self.valeur_si_vide = valeur_si_vide
        kwargs.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}))
        super().__init__(**kwargs)

    def prepare_value(self, value):
        if isinstance(value, int) and not isinstance(value, bool):
            return centimes_vers_saisie(value)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return self.valeur_si_vide
        try:
            centimes = parse_euros(value)
        except ValueError:
            raise forms.ValidationError(
                "Saisissez un montant en euros, par exemple 1 234,56.", code="invalide"
            ) from None
        if self.minimum is not None and centimes < self.minimum:
            if self.minimum == 1:
                raise forms.ValidationError("Le montant doit être supérieur à zéro.", code="minimum")
            raise forms.ValidationError(
                f"Le montant doit être au moins {format_euros(self.minimum)}.", code="minimum"
            )
        return centimes
