from django.db import models
from django.urls import reverse

from biens.models import Bien


class Pret(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="prets")
    banque = models.CharField("banque", max_length=100)
    libelle = models.CharField("libellé", max_length=100, blank=True)
    capital_emprunte = models.BigIntegerField("capital emprunté (centimes)")
    date_debut = models.DateField("date de début")

    class Meta:
        ordering = ["bien__nom", "date_debut"]
        verbose_name = "prêt"

    def __str__(self):
        return f"{self.banque} — {self.bien}"

    def get_absolute_url(self):
        return reverse("credit:detail", args=[self.pk])


class Echeance(models.Model):
    pret = models.ForeignKey(Pret, on_delete=models.CASCADE, related_name="echeances")
    date = models.DateField("date")
    capital = models.BigIntegerField("capital (centimes)", default=0)
    interets = models.BigIntegerField("intérêts (centimes)", default=0)
    assurance = models.BigIntegerField("assurance emprunteur (centimes)", default=0)
    frais = models.BigIntegerField("frais (centimes)", default=0)

    class Meta:
        ordering = ["date"]
        verbose_name = "échéance"
        constraints = [models.UniqueConstraint(fields=["pret", "date"], name="echeance_unique_par_date")]

    @property
    def deductible(self):
        return self.interets + self.assurance + self.frais
