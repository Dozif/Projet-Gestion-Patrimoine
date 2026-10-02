from django.urls import path

from . import views

app_name = "fiscalite"

urlpatterns = [
    path("copropriete/", views.copropriete, name="copropriete"),
    path("copropriete/<int:pk>/", views.modifier_decompte, name="modifier_decompte"),
    path("copropriete/<int:pk>/supprimer/", views.supprimer_decompte, name="supprimer_decompte"),
    path("deficits/", views.deficits, name="deficits"),
    path("deficits/<int:pk>/supprimer/", views.supprimer_deficit, name="supprimer_deficit"),
]
