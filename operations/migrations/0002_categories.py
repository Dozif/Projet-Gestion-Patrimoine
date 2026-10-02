from django.db import migrations

NOTICE = "Notice 2044"
CATEGORIES = [
    ("loyer", "Loyer encaissé", "RECETTE_IMPOSABLE", "211",
     "Loyer hors charges réellement encaissé, avant honoraires d'agence.", NOTICE),
    ("depenses-locataire", "Dépense du propriétaire payée par le locataire", "RECETTE_IMPOSABLE", "212",
     "Dépense incombant normalement au propriétaire et mise à la charge du locataire.", NOTICE),
    ("subvention", "Subvention ANAH ou indemnité pour travaux", "RECETTE_IMPOSABLE", "213", "", NOTICE),
    ("indemnite-assurance", "Indemnité d'assurance (perte de loyers)", "RECETTE_IMPOSABLE", "214", "", NOTICE),
    ("charges-locataire", "Provision ou remboursement de charges par le locataire", "RECETTE_NON_IMPOSABLE", "",
     "Non imposable : les charges récupérables refacturées au locataire ne sont pas des loyers.", NOTICE),
    ("depot-garantie", "Dépôt de garantie reçu", "RECETTE_NON_IMPOSABLE", "",
     "Non imposable tant qu'il n'est pas conservé pour couvrir des loyers impayés.", NOTICE),
    ("honoraires", "Honoraires d'agence et frais de gestion", "CHARGE_DEDUCTIBLE", "221",
     "Honoraires de gestion, de location et de rédaction de bail à la charge du propriétaire.",
     "BOFiP BOI-RFPI-BASE-20-10"),
    ("frais-procedure", "Frais de procédure, d'avocat ou d'huissier", "CHARGE_DEDUCTIBLE", "221", "",
     "BOFiP BOI-RFPI-BASE-20-10"),
    ("assurance-pno", "Assurance propriétaire non occupant ou loyers impayés", "CHARGE_DEDUCTIBLE", "223", "",
     NOTICE),
    ("travaux", "Travaux de réparation, d'entretien et d'amélioration", "CHARGE_DEDUCTIBLE", "224",
     "Déductibles sauf travaux de construction, de reconstruction ou d'agrandissement.",
     "BOFiP BOI-RFPI-BASE-20-30"),
    ("charges-non-recuperees", "Charges récupérables non récupérées", "CHARGE_DEDUCTIBLE", "225",
     "Charges récupérables restées à votre charge au départ du locataire.", NOTICE),
    ("indemnite-eviction", "Indemnité d'éviction ou frais de relogement", "CHARGE_DEDUCTIBLE", "226", "", NOTICE),
    ("taxe-fonciere", "Taxe foncière (hors ordures ménagères)", "CHARGE_DEDUCTIBLE", "227",
     "Saisissez la taxe d'enlèvement des ordures ménagères à part : elle n'est pas déductible.", NOTICE),
    ("provisions-copro", "Provisions de charges de copropriété (appels de fonds)", "CHARGE_DEDUCTIBLE", "229",
     "La part non déductible sera régularisée l'année suivante (décompte du syndic).", NOTICE),
    ("frais-emprunt", "Frais d'emprunt hors échéancier (dossier, garantie)", "INTERETS", "250",
     "Les intérêts et l'assurance des échéances viennent du tableau d'amortissement.",
     "BOFiP BOI-RFPI-BASE-20-80"),
    ("teom", "Taxe d'enlèvement des ordures ménagères", "CHARGE_NON_DEDUCTIBLE", "",
     "Récupérable sur le locataire, non déductible.", NOTICE),
    ("travaux-non-deductibles", "Travaux de construction, reconstruction ou agrandissement",
     "CHARGE_NON_DEDUCTIBLE", "", "", "BOFiP BOI-RFPI-BASE-20-30"),
    ("capital-emprunt", "Capital d'emprunt remboursé", "CHARGE_NON_DEDUCTIBLE", "",
     "Seuls les intérêts sont déductibles.", "BOFiP BOI-RFPI-BASE-20-80"),
    ("autre-non-deductible", "Autre dépense non déductible", "CHARGE_NON_DEDUCTIBLE", "", "", NOTICE),
]


def creer(apps, schema_editor):
    Categorie = apps.get_model("operations", "Categorie")
    Categorie.objects.bulk_create(
        Categorie(code=code, libelle=libelle, nature=nature, ligne_2044=ligne, aide=aide, source=source, ordre=i)
        for i, (code, libelle, nature, ligne, aide, source) in enumerate(CATEGORIES)
    )


def supprimer(apps, schema_editor):
    apps.get_model("operations", "Categorie").objects.filter(code__in=[c[0] for c in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]
    operations = [migrations.RunPython(creer, supprimer)]
