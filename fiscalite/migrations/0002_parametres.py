from django.db import migrations


def creer(apps, schema_editor):
    ParametresAnnuels = apps.get_model("fiscalite", "ParametresAnnuels")
    for annee in (2024, 2025, 2026):
        ParametresAnnuels.objects.get_or_create(
            annee=annee, defaults={"commentaire": "Valeurs par défaut : vérifier la TMI et les plafonds Pinel."}
        )


class Migration(migrations.Migration):
    dependencies = [("fiscalite", "0001_initial")]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
