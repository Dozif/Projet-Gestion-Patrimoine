from django.db import models


class DeclarationFigee(models.Model):
    annee = models.PositiveSmallIntegerField("année", unique=True)
    figee_le = models.DateTimeField("figée le", auto_now=True)
    donnees = models.JSONField("résultat figé")
    empreinte = models.CharField("empreinte", max_length=64)

    class Meta:
        ordering = ["-annee"]
        verbose_name = "déclaration figée"

    def __str__(self):
        return f"Déclaration {self.annee} figée"
