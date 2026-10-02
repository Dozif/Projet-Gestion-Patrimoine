from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path(
        "connexion/",
        auth_views.LoginView.as_view(
            template_name="comptes/connexion.html", redirect_authenticated_user=True
        ),
        name="connexion",
    ),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("double-authentification/", views.double_authentification, name="double_authentification"),
]
