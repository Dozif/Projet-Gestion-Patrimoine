from django.urls import path

from . import views

app_name = "declaration"

urlpatterns = [
    path("", views.declaration, name="declaration"),
    path("<int:annee>/csv/", views.export_csv, name="export_csv"),
]
