from django.contrib import admin
from django.urls import include, path

from declaration.views import tableau_de_bord

urlpatterns = [
    path("", tableau_de_bord, name="accueil"),
    path("compte/", include("comptes.urls")),
    path("biens/", include("biens.urls")),
    path("operations/", include("operations.urls")),
    path("credit/", include("credit.urls")),
    path("fiscalite/", include("fiscalite.urls")),
    path("declaration/", include("declaration.urls")),
    path("admin/", admin.site.urls),
]
