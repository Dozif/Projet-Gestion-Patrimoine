import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée le compte du propriétaire au premier démarrage (variables PATRIMOINE_ADMIN_*)."

    def handle(self, *args, **options):
        identifiant = os.environ.get("PATRIMOINE_ADMIN_UTILISATEUR", "").strip()
        mot_de_passe = os.environ.get("PATRIMOINE_ADMIN_MOT_DE_PASSE", "")
        if not identifiant or not mot_de_passe:
            self.stdout.write("Aucun compte à initialiser (variables PATRIMOINE_ADMIN_* absentes).")
            return
        Utilisateur = get_user_model()
        if Utilisateur.objects.exists():
            self.stdout.write("Un compte existe déjà : aucun compte n'est créé ni modifié.")
            return
        try:
            validate_password(mot_de_passe, Utilisateur(username=identifiant))
        except ValidationError as erreur:
            raise CommandError("Le mot de passe du .env est refusé : " + " ".join(erreur.messages)) from None
        Utilisateur.objects.create_superuser(identifiant, password=mot_de_passe)
        self.stdout.write(self.style.SUCCESS(f"Compte « {identifiant} » créé."))
