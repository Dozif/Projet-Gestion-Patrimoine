from base64 import b32encode
from hmac import compare_digest

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

PAGE = "comptes/double_authentification.html"
LONGUEUR_MIN_CODE = 16
ESSAIS_MAX = 5
# Le délai de django-otp double à chaque code faux, sans plafond pratique : avec le seul mot de passe, on pourrait
# tenir le propriétaire hors de l'application indéfiniment. Plafonné à 2**9 s, il rend toujours la force brute
# du code impraticable.
PLAFOND_ECHECS_TOTP = 10


def _etape_installation(request):
    """Avant d'afficher un QR code en production, exige le code d'installation du fichier .env."""
    if settings.PATRIMOINE_INSCRIPTION_LIBRE or request.session.get("installation_validee"):
        return None
    code_attendu = settings.PATRIMOINE_CODE_INSTALLATION
    if len(code_attendu) < LONGUEUR_MIN_CODE:
        return render(request, PAGE, {"ferme": True})
    erreur = None
    if request.method == "POST" and "code_installation" in request.POST:
        if compare_digest(request.POST["code_installation"].strip().encode(), code_attendu.encode()):
            # Un appareil non confirmé laissé par un enrôlement abandonné a déjà montré sa clé : on repart à neuf.
            TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
            request.session["installation_validee"] = True
            return redirect(request.get_full_path())
        essais = request.session.get("essais_installation", 0) + 1
        if essais >= ESSAIS_MAX:
            logout(request)
            messages.error(request, "Trop d'essais du code d'installation : reconnectez-vous.")
            return redirect("comptes:connexion")
        request.session["essais_installation"] = essais
        erreur = "Code d'installation incorrect."
    return render(request, PAGE, {"installation": True, "erreur": erreur})


def _blocage(appareil):
    """Message à afficher si l'appareil est en délai après des codes faux, sinon None."""
    appareil.throttling_failure_count = min(appareil.throttling_failure_count, PLAFOND_ECHECS_TOTP)
    autorise, info = appareil.verify_is_allowed()
    if autorise or "locked_until" not in (info or {}):
        return None
    return (
        f"Trop de codes incorrects : réessayez après {timezone.localtime(info['locked_until']):%H:%M:%S}. "
        "Si ces erreurs ne viennent pas de vous, quelqu'un connaît votre mot de passe : "
        "changez-le (guide d'installation, section « Secours »)."
    )


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
        erreur = _blocage(appareil)
        if erreur is None and code.isdigit() and appareil.verify_token(code):
            if configuration:
                appareil.confirmed = True
                appareil.save(update_fields=["confirmed"])
                request.session.pop("installation_validee", None)
            request.session.cycle_key()
            otp_login(request, appareil)
            suivant = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(
                suivant, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                suivant = reverse("accueil")
            return redirect(suivant)
        erreur = erreur or "Code incorrect. Vérifiez l'heure de votre téléphone et réessayez."
    contexte = {"configuration": configuration, "erreur": erreur}
    if configuration:
        image = qrcode.make(appareil.config_url, image_factory=qrcode.image.svg.SvgPathImage)
        contexte["qr_svg"] = image.to_string(encoding="unicode")
        contexte["cle"] = b32encode(appareil.bin_key).decode()
    return render(request, PAGE, contexte)
