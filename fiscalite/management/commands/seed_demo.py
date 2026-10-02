from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from biens.models import Bail, Bien, EngagementPinel, Locataire, PeriodePinel
from credit.models import Echeance, Pret
from fiscalite.models import Configuration, DecompteCopropriete, DeficitAnterieur
from operations.models import Categorie, Operation


class Command(BaseCommand):
    help = "Crée des données fictives de démonstration (base sans bien uniquement)."

    @transaction.atomic
    def handle(self, *args, **options):
        if Bien.objects.exists():
            raise CommandError("La base contient déjà des biens : seed_demo ne s'exécute que sur une base vide.")
        configuration = Configuration.charger()
        configuration.premiere_annee = 2025
        configuration.save()

        t2 = Bien.objects.create(
            nom="T2 Les Tilleuls", adresse="[Adresse fictive]", surface_habitable=Decimal("45"),
            surface_annexes=Decimal("7"), date_acquisition=date(2014, 11, 20), prix_revient=16_800_000,
        )
        t3 = Bien.objects.create(
            nom="T3 Centre", adresse="[Adresse fictive]", surface_habitable=Decimal("62"),
            date_acquisition=date(2019, 6, 3), prix_revient=19_500_000,
        )
        pinel = EngagementPinel.objects.create(
            bien=t2, date_mise_en_location=date(2015, 1, 1), duree_annees=12, zone="A",
            prix_revient=16_800_000, surface_habitable=Decimal("45"),
        )
        PeriodePinel.objects.create(engagement=pinel, annee_debut=2015, annee_fin=2023, taux_annuel=Decimal("2"))
        PeriodePinel.objects.create(engagement=pinel, annee_debut=2024, annee_fin=2026, taux_annuel=Decimal("1"))
        for bien, nom, loyer in ((t2, "Locataire A (fictif)", 62_000), (t3, "Locataire B (fictif)", 78_000)):
            Bail.objects.create(
                bien=bien, locataire=Locataire.objects.create(nom=nom), date_debut=date(2023, 9, 1),
                loyer_hc=loyer, provision_charges=4_000,
            )

        categories = {c.code: c for c in Categorie.objects.all()}

        def operation(bien, code, montant, jour, libelle):
            Operation.objects.create(
                bien=bien, categorie=categories[code], date_paiement=jour, montant=montant, libelle=libelle
            )

        for mois in range(1, 13):
            operation(t2, "loyer", 62_000, date(2025, mois, 5), f"Loyer {mois:02d}/2025")
            operation(t3, "loyer", 78_000, date(2025, mois, 5), f"Loyer {mois:02d}/2025")
        for bien, honoraires, assurance, taxe, appel in (
            (t2, 52_100, 14_800, 81_200, 24_000), (t3, 65_500, 17_500, 104_500, 33_000)
        ):
            operation(bien, "honoraires", honoraires, date(2025, 12, 31), "Honoraires d'agence 2025")
            operation(bien, "assurance-pno", assurance, date(2025, 5, 2), "Assurance propriétaire non occupant")
            operation(bien, "taxe-fonciere", taxe, date(2025, 10, 15), "Taxe foncière 2025 (hors TEOM)")
            operation(bien, "teom", 16_800, date(2025, 10, 15), "Taxe d'enlèvement des ordures ménagères")
            for mois in (1, 4, 7, 10):
                operation(bien, "provisions-copro", appel, date(2025, mois, 10), f"Appel de fonds {mois:02d}/2025")
        operation(t3, "travaux", 420_000, date(2025, 3, 12), "Rénovation de la salle d'eau")
        operation(t3, "travaux", 220_000, date(2025, 9, 20), "Remplacement de la cuisine")

        for bien, interets in ((t2, 218_000), (t3, 395_000)):
            pret = Pret.objects.create(
                bien=bien, banque="Banque fictive", capital_emprunte=15_000_000, date_debut=date(2015, 1, 5)
            )
            mensuel = interets // 12
            for mois in range(1, 13):
                reste = interets - mensuel * 12 if mois == 12 else 0
                Echeance.objects.create(pret=pret, date=date(2025, mois, 5), capital=61_245, interets=mensuel + reste)

        DecompteCopropriete.objects.create(bien=t2, annee=2024, part_non_deductible=21_000, commentaire="Fictif")
        DecompteCopropriete.objects.create(bien=t3, annee=2024, part_non_deductible=29_000, commentaire="Fictif")
        DeficitAnterieur.objects.create(annee_origine=2022, montant=240_000)
        DeficitAnterieur.objects.create(annee_origine=2023, montant=115_000)
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées (2 biens, année 2025)."))
