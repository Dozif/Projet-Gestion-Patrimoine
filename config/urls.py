from django.contrib import admin
from django.urls import include, path

from commun.views import accueil

urlpatterns = [
    path("", accueil, name="accueil"),
    path("compte/", include("comptes.urls")),
    path("admin/", admin.site.urls),
]
