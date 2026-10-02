from django.urls import NoReverseMatch, reverse

ENTREES = (
    ("accueil", "Tableau de bord"),
    ("biens:liste", "Biens"),
    ("operations:liste", "Opérations"),
    ("credit:liste", "Crédit"),
    ("fiscalite:copropriete", "Copropriété"),
    ("fiscalite:deficits", "Déficits"),
    ("admin:index", "Paramètres"),
)


def navigation(request):
    entrees = []
    for nom, libelle in ENTREES:
        try:
            url = reverse(nom)
        except NoReverseMatch:
            continue
        actif = request.path == url if url == "/" else request.path.startswith(url)
        entrees.append({"url": url, "libelle": libelle, "actif": actif})
    return {"navigation": entrees}
