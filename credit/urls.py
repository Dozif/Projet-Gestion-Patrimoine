from django.urls import path

from . import views

app_name = "credit"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/importer/", views.importer, name="importer"),
    path("<int:pk>/echeances/nouvelle/", views.ajouter_echeance, name="ajouter_echeance"),
    path("<int:pk>/echeances/<int:echeance_pk>/", views.modifier_echeance, name="modifier_echeance"),
    path("<int:pk>/echeances/<int:echeance_pk>/supprimer/", views.supprimer_echeance, name="supprimer_echeance"),
]
