import os
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Sauvegarde la base SQLite dans SAUVEGARDES_DIR et ne garde que les plus récentes."

    def add_arguments(self, parser):
        parser.add_argument("--garder", type=int, default=30, help="Nombre de sauvegardes conservées (30).")

    def handle(self, *args, garder, **options):
        dossier = Path(settings.SAUVEGARDES_DIR)
        dossier.mkdir(parents=True, exist_ok=True)
        # Les sessions expirées (qui peuvent contenir un CSV importé) n'ont rien à faire dans les sauvegardes.
        call_command("clearsessions")
        cible = dossier / f"patrimoine-{timezone.localtime():%Y%m%d-%H%M%S-%f}.sqlite3"
        # Fichier créé vide en 0600 avant d'y copier la base : il n'est jamais lisible par d'autres comptes.
        os.close(os.open(cible, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        connection.ensure_connection()
        copie = sqlite3.connect(cible)
        try:
            connection.connection.backup(copie)
        finally:
            copie.close()
        sauvegardes = sorted(dossier.glob("patrimoine-*.sqlite3"), key=lambda p: p.name, reverse=True)
        for ancienne in sauvegardes[garder:]:
            ancienne.unlink()
        conservees = min(len(sauvegardes), garder)
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde créée : {cible.name} ({conservees} conservées)."))
