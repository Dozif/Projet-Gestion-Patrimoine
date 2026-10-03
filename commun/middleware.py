from django.http import HttpResponse

# Un justificatif fait au plus 10 Mo : le reste du formulaire tient dans la marge.
TAILLE_MAX_CORPS = 12 * 1024 * 1024
# Avant la double authentification, seuls de petits formulaires (connexion, code) sont légitimes.
TAILLE_MAX_CORPS_NON_VERIFIE = 64 * 1024


class LimiteTailleRequete:
    """Refuse (413) un corps trop gros avant que CsrfViewMiddleware ou la vue ne le lise.

    Django ne plafonne pas la taille des fichiers d'un formulaire multipart et les écrit sur disque ;
    gunicorn non plus. À placer avant CsrfViewMiddleware : son process_view passe donc en premier,
    et request.user y est déjà disponible.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, vue, args, kwargs):
        try:
            taille = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            taille = 0
        verifie = request.user.is_authenticated and request.user.is_verified()
        limite = TAILLE_MAX_CORPS if verifie else TAILLE_MAX_CORPS_NON_VERIFIE
        if taille > limite:
            return HttpResponse("Requête trop volumineuse.", status=413, content_type="text/plain; charset=utf-8")
        return None
