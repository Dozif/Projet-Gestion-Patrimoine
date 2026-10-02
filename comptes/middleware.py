from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

CHEMINS_LIBRES = ("comptes:connexion", "comptes:deconnexion", "comptes:double_authentification")


class DoubleAuthentificationObligatoire:
    """Redirige tout utilisateur connecté mais non vérifié par TOTP vers la double authentification."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.is_verified():
            libres = {reverse(nom) for nom in CHEMINS_LIBRES}
            statique = "/" + settings.STATIC_URL.lstrip("/")
            if request.path not in libres and not request.path.startswith(statique):
                cible = reverse("comptes:double_authentification")
                return redirect(f"{cible}?next={quote(request.get_full_path())}")
        return self.get_response(request)
