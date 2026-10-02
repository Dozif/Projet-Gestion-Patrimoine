from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

import fiscal
from biens.models import Bien


class ParametresAnnuels(models.Model):
    annee = models.PositiveSmallIntegerField("année", unique=True)
    plafond_imputation = models.BigIntegerField(
        "plafond d'imputation sur le revenu global (centimes)", default=1_070_000
    )
    forfait_gestion = models.BigIntegerField("forfait de gestion par local, ligne 222 (centimes)", default=2_000)
    taux_prelevements_sociaux = models.DecimalField(
        "taux des prélèvements sociaux (%)", max_digits=5, decimal_places=2, default=Decimal("17.20")
    )
    tmi = models.DecimalField(
        "tranche marginale d'imposition du foyer (%)", max_digits=5, decimal_places=2, default=Decimal("30")
    )
    plafonds_pinel_m2 = models.JSONField(
        "plafonds de loyer Pinel (centimes par m², par zone)", default=dict, blank=True,
        help_text='Exemple : {"A": 1349, "B1": 1087} — à reprendre du BOFiP de l\'année.',
    )
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        ordering = ["-annee"]
        verbose_name = "paramètres annuels"
        verbose_name_plural = "paramètres annuels"

    def __str__(self):
        return f"Paramètres {self.annee}"

    def clean(self):
        plafonds = self.plafonds_pinel_m2
        valides = isinstance(plafonds, dict) and all(
            isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in plafonds.values()
        )
        if not valides:
            raise ValidationError({
                "plafonds_pinel_m2": 'Indiquez les plafonds en centimes entiers par m², par zone : {"A": 1349}.'
            })

    def vers_fiscal(self) -> fiscal.ParametresAnnuels:
        return fiscal.ParametresAnnuels(
            annee=self.annee, plafond_imputation_revenu_global=self.plafond_imputation,
            forfait_gestion_par_local=self.forfait_gestion,
        )


class Configuration(models.Model):
    premiere_annee = models.PositiveSmallIntegerField("première année gérée par l'application", default=2025)

    class Meta:
        verbose_name = "configuration"

    def __str__(self):
        return "Configuration"

    @classmethod
    def charger(cls) -> "Configuration":
        configuration, _ = cls.objects.get_or_create(pk=1)
        return configuration


class DecompteCopropriete(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="decomptes")
    annee = models.PositiveSmallIntegerField("année du décompte")
    part_non_deductible = models.BigIntegerField(
        "part non déductible des provisions (centimes)",
        help_text="Charges récupérables et dépenses non déductibles indiquées par le syndic.",
    )
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        ordering = ["-annee", "bien__nom"]
        verbose_name = "décompte de copropriété"
        constraints = [models.UniqueConstraint(fields=["bien", "annee"], name="decompte_unique_par_annee")]

    def __str__(self):
        return f"Décompte {self.annee} — {self.bien}"


class DeficitAnterieur(models.Model):
    annee_origine = models.PositiveSmallIntegerField("année d'origine", unique=True)
    montant = models.BigIntegerField("solde restant à imputer (centimes)", validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["annee_origine"]
        verbose_name = "déficit antérieur"

    def __str__(self):
        return f"Déficit {self.annee_origine}"

    def clean(self):
        premiere = Configuration.charger().premiere_annee
        if self.annee_origine is not None and self.annee_origine >= premiere:
            raise ValidationError(
                {"annee_origine": f"Le déficit doit être antérieur à la première année gérée ({premiere})."}
            )
