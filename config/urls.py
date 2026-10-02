from django.contrib import admin
from django.urls import include, path

from commun.views import accueil

urlpatterns = [
    path("", accueil, name="accueil"),
    path("compte/", include("comptes.urls")),
    path("biens/", include("biens.urls")),
    path("operations/", include("operations.urls")),
    path("credit/", include("credit.urls")),
    path("fiscalite/", include("fiscalite.urls")),
    path("admin/", admin.site.urls),
]
