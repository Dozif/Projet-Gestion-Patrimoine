from django.urls import path

from . import views

app_name = "declaration"

urlpatterns = [
    path("<int:annee>/csv/", views.export_csv, name="export_csv"),
]
