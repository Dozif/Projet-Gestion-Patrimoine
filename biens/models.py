from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

import fiscal


class RegimeFiscal(models.TextChoices):
    FONCIER_REEL = "FONCIER_REEL", "Location vide — régime réel"


class Bien(models.Model):
    nom = models.CharField("nom", max_length=100, unique=True)
    adresse = models.TextField("adresse", blank=True)
    surface_habitable = models.DecimalField("surface habitable (m²)", max_digits=6, decimal_places=2)
    surface_annexes = models.DecimalField(
        "surface des annexes (m²)", max_digits=6, decimal_places=2, default=0
    )
    date_acquisition = models.DateField("date d'acquisition", null=True, blank=True)
    prix_revient = models.BigIntegerField("prix de revient (centimes)", default=0)
    regime = models.CharField(
        "régime fiscal", max_length=30, choices=RegimeFiscal.choices, default=RegimeFiscal.FONCIER_REEL
    )
    nb_locaux = models.PositiveSmallIntegerField(
        "nombre de locaux", default=1, validators=[MinValueValidator(1)]
    )
    actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse("biens:detail", args=[self.pk])

    def vers_fiscal(self) -> fiscal.Bien:
        return fiscal.Bien(id=self.pk, nom=self.nom, regime=self.regime, nb_locaux=self.nb_locaux)

    def bail_en_cours(self, jour):
        return (
            self.baux.filter(date_debut__lte=jour)
            .filter(models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=jour))
            .order_by("-date_debut")
            .first()
        )


class EngagementPinel(models.Model):
    ZONES = [("A bis", "A bis"), ("A", "A"), ("B1", "B1"), ("B2", "B2"), ("C", "C")]

    bien = models.OneToOneField(Bien, on_delete=models.CASCADE, related_name="pinel")
    date_mise_en_location = models.DateField("date de mise en location")
    duree_annees = models.PositiveSmallIntegerField(
        "durée de l'engagement", choices=[(6, "6 ans"), (9, "9 ans"), (12, "12 ans")]
    )
    zone = models.CharField("zone", max_length=10, choices=ZONES)
    prix_revient = models.BigIntegerField("prix de revient retenu (centimes)")
    surface_habitable = models.DecimalField("surface habitable retenue (m²)", max_digits=6, decimal_places=2)

    def __str__(self):
        return f"Pinel — {self.bien}"

    def vers_fiscal(self) -> fiscal.EngagementPinel:
        return fiscal.EngagementPinel(
            self.date_mise_en_location, self.duree_annees, self.prix_revient, self.surface_habitable,
            tuple(p.vers_fiscal() for p in self.periodes.all()),
        )


class PeriodePinel(models.Model):
    engagement = models.ForeignKey(EngagementPinel, on_delete=models.CASCADE, related_name="periodes")
    annee_debut = models.PositiveSmallIntegerField("année de début")
    annee_fin = models.PositiveSmallIntegerField("année de fin")
    taux_annuel = models.DecimalField("taux annuel (%)", max_digits=4, decimal_places=2)

    class Meta:
        ordering = ["annee_debut"]

    def vers_fiscal(self) -> fiscal.PeriodePinel:
        return fiscal.PeriodePinel(self.annee_debut, self.annee_fin, self.taux_annuel)


class Locataire(models.Model):
    nom = models.CharField("nom", max_length=150)
    email = models.EmailField("e-mail", blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    revenu_fiscal_reference = models.BigIntegerField(
        "revenu fiscal de référence à la signature (centimes)", null=True, blank=True
    )
    nb_personnes_foyer = models.PositiveSmallIntegerField("personnes dans le foyer", null=True, blank=True)

    def __str__(self):
        return self.nom


class Bail(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="baux")
    locataire = models.ForeignKey(Locataire, on_delete=models.PROTECT, related_name="baux")
    date_debut = models.DateField("début")
    date_fin = models.DateField("fin", null=True, blank=True)
    loyer_hc = models.BigIntegerField("loyer mensuel hors charges (centimes)")
    provision_charges = models.BigIntegerField("provision mensuelle sur charges (centimes)", default=0)
    depot_garantie = models.BigIntegerField("dépôt de garantie (centimes)", default=0)

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.bien} — {self.locataire}"

    def clean(self):
        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La fin du bail doit être postérieure à son début."})
