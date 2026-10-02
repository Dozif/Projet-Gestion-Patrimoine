from base64 import b32encode

import qrcode
import qrcode.image.svg
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


def double_authentification(request):
    if request.user.is_verified():
        return redirect("accueil")
    appareil = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    configuration = appareil is None
    if configuration:
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
    return render(request, "comptes/double_authentification.html", contexte)
