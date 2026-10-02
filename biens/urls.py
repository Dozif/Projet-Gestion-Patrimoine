from django.urls import path

from . import views

app_name = "biens"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/pinel/", views.pinel, name="pinel"),
    path("<int:pk>/baux/nouveau/", views.creer_bail, name="creer_bail"),
    path("<int:pk>/baux/<int:bail_pk>/", views.modifier_bail, name="modifier_bail"),
]
