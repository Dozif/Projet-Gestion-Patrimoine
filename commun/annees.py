ANNEE_MIN = 2000
ANNEE_MAX = 2100


def annee_demandee(request, defaut: int) -> int:
    """Année passée dans `?annee=` si elle est plausible, sinon `defaut`."""
    try:
        annee = int(request.GET.get("annee", ""))
    except ValueError:
        return defaut
    return annee if ANNEE_MIN <= annee <= ANNEE_MAX else defaut
