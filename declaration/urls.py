from django.urls import path, register_converter

from . import views


class AnneeConverter:
    """Année sur 4 chiffres : une valeur démesurée donne un 404 au lieu d'atteindre le calcul."""

    regex = "[0-9]{4}"

    def to_python(self, valeur):
        return int(valeur)

    def to_url(self, valeur):
        return f"{valeur:04d}"


register_converter(AnneeConverter, "annee")

app_name = "declaration"

urlpatterns = [
    path("", views.declaration, name="declaration"),
    path("<annee:annee>/csv/", views.export_csv, name="export_csv"),
    path("<annee:annee>/figer/", views.figer, name="figer"),
    path("<annee:annee>/defiger/", views.defiger, name="defiger"),
]
