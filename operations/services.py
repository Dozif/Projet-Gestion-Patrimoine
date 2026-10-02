from django.db import transaction

from .models import Categorie, Operation, ReleveAgence


@transaction.atomic
def enregistrer_releve(releve: ReleveAgence) -> list[Operation]:
    """Enregistre le relevé et remplace ses opérations (loyer, charges, honoraires)."""
    releve.save()
    releve.operations.all().delete()
    mois = f"{releve.periode:%m/%Y}"
    lignes = [
        ("loyer", releve.loyer_brut, f"Relevé agence {mois} — loyer"),
        ("charges-locataire", releve.charges_recues, f"Relevé agence {mois} — charges"),
        ("honoraires", releve.honoraires, f"Relevé agence {mois} — honoraires"),
    ]
    return [
        Operation.objects.create(
            bien=releve.bien, categorie=Categorie.objects.get(code=code), date_paiement=releve.date_versement,
            montant=montant, libelle=libelle, releve=releve,
        )
        for code, montant, libelle in lignes
        if montant > 0
    ]
