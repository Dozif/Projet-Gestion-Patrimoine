from datetime import date
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

import fiscal
from biens.models import Bien

EXTENSIONS_JUSTIFICATIF = {".pdf", ".jpg", ".jpeg", ".png"}
TAILLE_MAX_JUSTIFICATIF = 10 * 1024 * 1024


class NatureOperation(models.TextChoices):
    RECETTE_IMPOSABLE = "RECETTE_IMPOSABLE", "Recette imposable"
    RECETTE_NON_IMPOSABLE = "RECETTE_NON_IMPOSABLE", "Non imposable"
    CHARGE_DEDUCTIBLE = "CHARGE_DEDUCTIBLE", "Déductible"
    CHARGE_NON_DEDUCTIBLE = "CHARGE_NON_DEDUCTIBLE", "Non déductible"
    INTERETS = "INTERETS", "Intérêts · déductible"


CLASSES_BADGE = {
    NatureOperation.RECETTE_IMPOSABLE: "ri",
    NatureOperation.RECETTE_NON_IMPOSABLE: "ni",
    NatureOperation.CHARGE_DEDUCTIBLE: "d",
    NatureOperation.INTERETS: "d",
    NatureOperation.CHARGE_NON_DEDUCTIBLE: "nd",
}


# Premiers octets attendus pour chaque extension : un fichier HTML ou SVG renommé en .pdf ou .png est refusé.
SIGNATURES_JUSTIFICATIF = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def valider_justificatif(fichier):
    extension = Path(fichier.name).suffix.lower()
    if extension not in EXTENSIONS_JUSTIFICATIF:
        raise ValidationError("Formats acceptés : PDF, JPEG ou PNG.")
    if fichier.size > TAILLE_MAX_JUSTIFICATIF:
        raise ValidationError("Le justificatif ne doit pas dépasser 10 Mo.")
    fichier.seek(0)
    debut = fichier.read(8)
    fichier.seek(0)
    if not debut.startswith(SIGNATURES_JUSTIFICATIF[extension]):
        raise ValidationError("Le contenu du fichier ne correspond pas à son extension (PDF, JPEG ou PNG).")


def chemin_justificatif(instance, nom_fichier):
    annee = instance.date_paiement.year if instance.date_paiement else date.today().year
    return f"{annee}/{uuid4().hex}{Path(nom_fichier).suffix.lower()}"


class Categorie(models.Model):
    code = models.SlugField("code", unique=True)
    libelle = models.CharField("libellé", max_length=150)
    nature = models.CharField("nature", max_length=30, choices=NatureOperation.choices)
    ligne_2044 = models.CharField("ligne 2044", max_length=3, blank=True, default="")
    aide = models.TextField("aide", blank=True)
    source = models.CharField("source", max_length=150, blank=True)
    active = models.BooleanField("active", default=True)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        ordering = ["ordre", "libelle"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.libelle

    @property
    def libelle_complet(self):
        ligne = f", ligne {self.ligne_2044}" if self.ligne_2044 else ""
        return f"{self.libelle} ({self.get_nature_display().lower()}{ligne})"

    @property
    def classe_badge(self):
        return CLASSES_BADGE[self.nature]

    def clean(self):
        try:
            fiscal.Operation(
                id=0, bien_id=0, date_paiement=date(2000, 1, 1), montant=1, nature=self.nature,
                ligne_2044=self.ligne_2044 or None,
            )
        except ValueError as erreur:
            raise ValidationError({"ligne_2044": str(erreur)}) from None


class ReleveAgence(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="releves")
    periode = models.DateField("mois concerné")
    date_versement = models.DateField("date du versement")
    loyer_brut = models.BigIntegerField("loyer brut (centimes)")
    charges_recues = models.BigIntegerField("charges reçues du locataire (centimes)", default=0)
    honoraires = models.BigIntegerField("honoraires retenus (centimes)", default=0)
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        ordering = ["-periode"]
        verbose_name = "relevé d'agence"
        constraints = [models.UniqueConstraint(fields=["bien", "periode"], name="releve_unique_par_mois")]

    def __str__(self):
        return f"Relevé {self.periode:%m/%Y} — {self.bien}"

    @property
    def net_verse(self):
        return self.loyer_brut + self.charges_recues - self.honoraires


class Operation(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="operations")
    categorie = models.ForeignKey(Categorie, on_delete=models.PROTECT, related_name="operations")
    date_paiement = models.DateField("date de paiement")
    montant = models.BigIntegerField("montant (centimes)", validators=[MinValueValidator(1)])
    libelle = models.CharField("libellé", max_length=200)
    justificatif = models.FileField(
        "justificatif", upload_to=chemin_justificatif, blank=True, validators=[valider_justificatif]
    )
    commentaire = models.TextField("commentaire", blank=True)
    releve = models.ForeignKey(
        ReleveAgence, on_delete=models.CASCADE, null=True, blank=True, related_name="operations"
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_paiement", "-id"]
        verbose_name = "opération"

    def __str__(self):
        return f"{self.date_paiement:%d/%m/%Y} — {self.libelle}"

    def vers_fiscal(self) -> fiscal.Operation:
        return fiscal.Operation(
            id=self.pk, bien_id=self.bien_id, date_paiement=self.date_paiement, montant=self.montant,
            nature=self.categorie.nature, ligne_2044=self.categorie.ligne_2044 or None, libelle=self.libelle,
        )
