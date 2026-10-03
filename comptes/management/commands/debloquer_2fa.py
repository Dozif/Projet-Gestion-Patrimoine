from django.core.management.base import BaseCommand
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = (
        "Secours : remet à zéro le délai de la double authentification ; avec --supprimer-appareil "
        "(téléphone perdu), supprime l'appareil pour permettre un nouvel enrôlement."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--supprimer-appareil", action="store_true",
            help="Supprime l'application d'authentification enregistrée (téléphone perdu ou changé).",
        )

    def handle(self, *args, supprimer_appareil, **options):
        if supprimer_appareil:
            nombre, _ = TOTPDevice.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(
                f"{nombre} appareil(s) supprimé(s). Remettez un code d'installation dans .env, recréez le "
                "conteneur, puis reconnectez-vous pour enrôler le nouveau téléphone."
            ))
            return
        nombre = TOTPDevice.objects.update(throttling_failure_count=0, throttling_failure_timestamp=None)
        self.stdout.write(self.style.SUCCESS(f"Délai remis à zéro ({nombre} appareil(s))."))
