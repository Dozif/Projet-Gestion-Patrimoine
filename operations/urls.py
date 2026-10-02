from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouvelle/", views.creer, name="creer"),
    path("<int:pk>/", views.modifier, name="modifier"),
    path("<int:pk>/supprimer/", views.supprimer, name="supprimer"),
    path("<int:pk>/justificatif/", views.justificatif, name="justificatif"),
    path("releves/nouveau/", views.creer_releve, name="creer_releve"),
    path("releves/<int:pk>/", views.modifier_releve, name="modifier_releve"),
]
