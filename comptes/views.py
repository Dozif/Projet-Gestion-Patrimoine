from base64 import b32encode
from hmac import compare_digest

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

PAGE = "comptes/double_authentification.html"


def _etape_installation(request):
    """Avant d'afficher un QR code en production, exige le code d'installation du fichier .env."""
    if settings.PATRIMOINE_INSCRIPTION_LIBRE or request.session.get("installation_validee"):
        return None
    code_attendu = settings.PATRIMOINE_CODE_INSTALLATION
    if not code_attendu:
        return render(request, PAGE, {"ferme": True})
    erreur = None
    if request.method == "POST" and "code_installation" in request.POST:
        if compare_digest(request.POST["code_installation"].strip().encode(), code_attendu.encode()):
            request.session["installation_validee"] = True
            return redirect(request.get_full_path())
        erreur = "Code d'installation incorrect."
    return render(request, PAGE, {"installation": True, "erreur": erreur})


def double_authentification(request):
    if request.user.is_verified():
        return redirect("accueil")
    appareil = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    configuration = appareil is None
    if configuration:
        reponse = _etape_installation(request)
        if reponse is not None:
            return reponse
        appareil, _ = TOTPDevice.objects.get_or_create(
            user=request.user, confirmed=False, defaults={"name": "Application d'authentification"}
        )
    erreur = None
    if request.method == "POST":
        code = request.POST.get("code", "").replace(" ", "")
        if code.isdigit() and appareil.verify_token(code):
            if configuration:
                appareil.confirmed = True
                appareil.save(update_fields=["confirmed"])
            otp_login(request, appareil)
            suivant = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(
                suivant, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                suivant = reverse("accueil")
            return redirect(suivant)
        erreur = "Code incorrect. Vérifiez l'heure de votre téléphone et réessayez."
    contexte = {"configuration": configuration, "erreur": erreur}
    if configuration:
        image = qrcode.make(appareil.config_url, image_factory=qrcode.image.svg.SvgPathImage)
        contexte["qr_svg"] = image.to_string(encoding="unicode")
        contexte["cle"] = b32encode(appareil.bin_key).decode()
    return render(request, PAGE, contexte)
