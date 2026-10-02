# Tableau de bord et déclaration (plan 3/4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher les résultats du moteur fiscal : tableau de bord chiffré de l'année (cartes par bien, loyers mois par mois, alertes, Pinel, estimation d'impôt), écran Déclaration 2044 ligne par ligne avec le détail de chaque montant, cases 2042, export CSV, impression PDF, déclaration figée avec alerte de modification, et saisie manuelle des échéances de prêt.

**Architecture:** Nouvelle application `declaration` : `presentation.py` (fonctions pures qui mettent en forme `ResultatFoncier` + `ContexteFiscal` : lignes, détail, cases, estimation, sérialisation, empreinte, CSV), `suivi.py` (loyers mois par mois, résumé Pinel, alertes — lit la base), `models.py` (`DeclarationFigee`), vues et gabarits. Toutes les vues passent par `fiscalite.services.calculer_annee()` (plan 2). Le PDF est produit par l'impression du navigateur (feuille de style `@media print`), sans dépendance supplémentaire.

**Tech Stack:** Django 5.2, pytest-django, ruff (line-length 120). Aucune nouvelle dépendance.

**Spec:** `docs/superpowers/specs/2026-10-02-gestion-patrimoine-design.md` (sections 5.2 à 5.4, 6 écrans 2, 5, 8). Plans précédents fusionnés : `docs/superpowers/plans/2026-10-02-moteur-fiscal.md`, `docs/superpowers/plans/2026-10-02-application-django.md`.

## Global Constraints

- Montants : centimes entiers jusqu'à l'affichage. Écran Déclaration et export CSV en **euros arrondis** (`fiscal.en_euros`, filtre `euros_entiers`) ; tableau de bord en euros et centimes (filtre `euros`).
- Toute vue passe par le contrôle d'accès existant (connexion + double authentification) ; aucune exception.
- Année demandée dans l'URL (`?annee=`) : entier entre 2000 et 2100, sinon l'année par défaut de l'écran — jamais d'erreur 500.
- `ParametresManquants` ou année antérieure à la première année gérée (`ValueError`) → message lisible sur la page, pas d'erreur 500 ; pour l'export CSV, 404.
- Textes en français ; Django `>=5.2,<5.3` ; `ruff check --fix .` propre ; commandes depuis `E:/Projet-Gestion-Patrimoine` avec `.venv/Scripts/python.exe`.
- Ligne 230 affichée **en négatif** (elle diminue les frais) ; les autres lignes en positif.
- Les fichiers de plus de quelques lignes s'écrivent avec l'outil d'écriture de fichiers, pas par `cat <<EOF` (les apostrophes cassent l'interpréteur de commandes de cet environnement).

## Review Focus

- Année farfelue dans l'URL (`?annee=abc`, `99999`, `0`) sur le tableau de bord, la déclaration et la liste des opérations → page affichée avec l'année par défaut (tests Task 1).
- Paramètres fiscaux de l'année absents, ou année antérieure à la première année gérée → message explicite sur le tableau de bord et la déclaration, 404 pour le CSV (tests Task 4, 5, 6).
- Base sans aucun bien → tableau de bord et déclaration s'affichent sans erreur (tests Task 4, 6).
- Données modifiées après avoir figé une déclaration → alerte visible ; aucune alerte si rien n'a changé (tests Task 7).
- Échéance saisie à la main à une date déjà occupée pour ce prêt → message d'erreur, pas d'erreur d'intégrité (test Task 8).

## File Structure

```text
commun/annees.py                      # annee_demandee()
commun/templatetags/montants.py       # + filtre euros_entiers (modifié)
operations/views.py                   # utilise annee_demandee (modifié)
declaration/__init__.py apps.py
declaration/presentation.py           # fonctions pures de mise en forme + CSV
declaration/suivi.py                  # loyers mois par mois, Pinel, alertes
declaration/models.py                 # DeclarationFigee
declaration/views.py urls.py
declaration/migrations/__init__.py 0001_initial.py (générée en Task 7)
templates/declaration/tableau_de_bord.html declaration.html
static/css/app.css                    # styles tableau de bord, déclaration, impression (modifié)
credit/forms.py views.py urls.py      # saisie manuelle des échéances (modifiés)
templates/credit/detail.html          # liens de saisie (modifié)
tests/commun/test_annees.py tests/declaration/…  tests/credit/test_echeances.py
```

Supprimés en Task 4 : `commun/views.py`, `templates/accueil.html` (remplacés par le tableau de bord).

---

### Task 1: Année demandée et euros arrondis

**Files:**
- Create: `commun/annees.py`
- Modify: `commun/templatetags/montants.py`, `operations/views.py`
- Test: `tests/commun/test_annees.py`

**Interfaces:**
- Produces: `annee_demandee(request, defaut: int) -> int` (lit `request.GET["annee"]`, entier entre `ANNEE_MIN = 2000` et `ANNEE_MAX = 2100`, sinon `defaut`) ; filtre `{{ centimes|euros_entiers }}` (arrondi à l'euro, `—` si `None`).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/commun/test_annees.py`

```python
import pytest
from django.template import Context, Template
from django.urls import reverse

from commun.annees import annee_demandee


@pytest.mark.parametrize("requete,attendu", [("?annee=2025", 2025), ("?annee=abc", 2026), ("?annee=99999", 2026), ("", 2026)])
def test_annee_demandee(rf, requete, attendu):
    assert annee_demandee(rf.get("/" + requete), 2026) == attendu


@pytest.mark.django_db
def test_liste_des_operations_avec_une_annee_farfelue(client_verifie):
    assert client_verifie.get(reverse("operations:liste") + "?annee=99999").status_code == 200


def test_filtre_euros_entiers():
    gabarit = Template("{% load montants %}{{ a|euros_entiers }}|{{ b|euros_entiers }}|{{ c|euros_entiers }}")
    assert gabarit.render(Context({"a": 15050, "b": -90600, "c": None})) == "151 €|−906 €|—"
```

Run: `.venv/Scripts/python.exe -m pytest tests/commun/test_annees.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'commun.annees'`.

- [ ] **Step 2: Implémenter**

`commun/annees.py` :

```python
ANNEE_MIN = 2000
ANNEE_MAX = 2100


def annee_demandee(request, defaut: int) -> int:
    """Année passée dans `?annee=` si elle est plausible, sinon `defaut`."""
    try:
        annee = int(request.GET.get("annee", ""))
    except ValueError:
        return defaut
    return annee if ANNEE_MIN <= annee <= ANNEE_MAX else defaut
```

Dans `commun/templatetags/montants.py`, remplacer l'import par `from commun.montants import format_euros` + `from fiscal import en_euros`, puis ajouter :

```python
@register.filter
def euros_entiers(centimes):
    return "—" if centimes is None else format_euros(en_euros(centimes) * 100)
```

Dans `operations/views.py`, ajouter `from commun.annees import annee_demandee` et remplacer le bloc :

```python
    try:
        annee = int(request.GET.get("annee") or (annees[0] if annees else date.today().year))
    except ValueError:
        annee = date.today().year
```

par :

```python
    annee = annee_demandee(request, annees[0] if annees else date.today().year)
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `167 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(commun): année demandée bornée et euros arrondis"
```

---

### Task 2: Mise en forme des résultats (fonctions pures)

**Files:**
- Create: `declaration/__init__.py`, `declaration/apps.py`, `declaration/migrations/__init__.py`, `declaration/presentation.py`
- Modify: `config/settings.py` (ajouter `"declaration",` à la fin d'`INSTALLED_APPS`)
- Test: `tests/declaration/__init__.py`, `tests/declaration/test_presentation.py`

**Interfaces:**
- Consumes: `fiscal.ResultatFoncier`, `fiscal.calcul_2044.LIGNES` (code → (libellé, règle, source)), `fiscalite.services.ContexteFiscal` (`biens`, `operations`, `sources`), commande `seed_demo`.
- Produces (`declaration.presentation`) : `ORDRE` (codes affichés), `colonnes_biens(resultat, contexte) -> list[str]` ; `lignes_declaration(resultat) -> list[dict]` (clés `code`, `libelle`, `valeurs` (liste par bien, 230 en négatif), `total`, `type` ∈ `ligne|total|resultat` ; lignes nulles masquées sauf 211, 215, 240, 250 ; dernière ligne « Résultat foncier » de code `""`) ; `detail_ligne(resultat, contexte, code) -> dict | None` (clés `code`, `libelle`, `regle`, `source`, `operations` (liste de `{"texte", "montant"}`), `total`) ; `cases_2042(resultat) -> list[dict]` (`code`, `libelle`, `montant`) ; `estimation_impot(revenu_net: int, deficit_global: int, tmi: Decimal, taux_ps: Decimal) -> dict` (`impot`, `economie`, centimes) ; `resultat_vers_dict(resultat, contexte) -> dict` (JSON) ; `empreinte(donnees: dict) -> str` (SHA-256).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/declaration/test_presentation.py` (+ `tests/declaration/__init__.py` vide)

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from declaration.presentation import (
    cases_2042,
    colonnes_biens,
    detail_ligne,
    empreinte,
    estimation_impot,
    lignes_declaration,
    resultat_vers_dict,
)
from fiscalite.services import calculer_annee
from operations.models import Categorie, Operation

pytestmark = pytest.mark.django_db


@pytest.fixture
def calcul_2025():
    call_command("seed_demo")
    return calculer_annee(2025)


def test_lignes_de_la_declaration(calcul_2025):
    resultat, _ = calcul_2025
    lignes = {l["code"]: l for l in lignes_declaration(resultat)}
    assert lignes["211"]["valeurs"] == [744_000, 936_000]
    assert lignes["211"]["total"] == 1_680_000
    assert lignes["230"]["valeurs"] == [-21_000, -29_000]
    assert lignes["240"]["type"] == "total"
    assert "212" not in lignes
    assert lignes[""]["valeurs"] == [300_900, -391_500]
    assert lignes[""]["type"] == "resultat"


def test_colonnes_dans_l_ordre_des_biens(calcul_2025):
    assert colonnes_biens(*calcul_2025) == ["T2 Les Tilleuls", "T3 Centre"]


def test_detail_des_travaux(calcul_2025):
    detail = detail_ligne(*calcul_2025, "224")
    assert detail["total"] == 640_000
    assert "agrandissement" in detail["regle"]
    assert sorted(o["montant"] for o in detail["operations"]) == [220_000, 420_000]
    assert any("Rénovation de la salle d'eau" in o["texte"] for o in detail["operations"])


def test_detail_des_interets_par_echeance(calcul_2025):
    assert len(detail_ligne(*calcul_2025, "250")["operations"]) == 24


def test_detail_d_une_ligne_inconnue(calcul_2025):
    assert detail_ligne(*calcul_2025, "999") is None


@pytest.mark.parametrize(
    "revenu,deficit,attendu", [(100_000, 0, {"impot": 47_200, "economie": 0}), (0, 90_600, {"impot": 0, "economie": 27_180})]
)
def test_estimation_impot(revenu, deficit, attendu):
    assert estimation_impot(revenu, deficit, Decimal("30"), Decimal("17.2")) == attendu


def test_cases_2042(calcul_2025):
    resultat, _ = calcul_2025
    assert [(c["code"], c["montant"]) for c in cases_2042(resultat)] == [
        ("4BA", 0), ("4BB", 0), ("4BC", 90_600), ("4BD", 355_000)
    ]


def test_serialisation_et_empreinte_stable(calcul_2025):
    donnees = resultat_vers_dict(*calcul_2025)
    assert donnees["cases"]["4BC"] == 90_600
    assert donnees["biens"][0]["nom"] == "T2 Les Tilleuls"
    assert empreinte(donnees) == empreinte(resultat_vers_dict(*calculer_annee(2025)))


def test_empreinte_change_si_les_donnees_changent(calcul_2025):
    avant = empreinte(resultat_vers_dict(*calcul_2025))
    t3 = calcul_2025[1].biens[1]
    Operation.objects.create(
        bien_id=t3.id, categorie=Categorie.objects.get(code="travaux"), date_paiement=date(2025, 11, 2),
        montant=10_000, libelle="Peinture",
    )
    assert empreinte(resultat_vers_dict(*calculer_annee(2025))) != avant
```

Run: `.venv/Scripts/python.exe -m pytest tests/declaration -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'declaration'`.

- [ ] **Step 2: Implémenter**

`declaration/apps.py` :

```python
from django.apps import AppConfig


class DeclarationConfig(AppConfig):
    name = "declaration"
    verbose_name = "Déclaration"
```

`declaration/__init__.py` et `declaration/migrations/__init__.py` vides ; ajouter `"declaration",` à la fin d'`INSTALLED_APPS`.

`declaration/presentation.py` :

```python
"""Mise en forme des résultats du moteur fiscal pour les écrans et les exports."""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from fiscal.calcul_2044 import LIGNES

ORDRE = ("211", "212", "213", "214", "215", "221", "222", "223", "224", "225", "226", "227", "229", "230", "240", "250")
TOUJOURS = frozenset({"211", "215", "240", "250"})
TOTAUX = frozenset({"215", "240"})
CASES = (
    ("4BA", "Revenu foncier imposable", "case_4ba"),
    ("4BB", "Déficit imputable sur les revenus fonciers", "case_4bb"),
    ("4BC", "Déficit imputable sur le revenu global", "case_4bc"),
    ("4BD", "Déficits antérieurs non encore imputés", "case_4bd"),
)


def colonnes_biens(resultat, contexte) -> list[str]:
    noms = {b.id: b.nom for b in contexte.biens}
    return [noms[r.bien_id] for r in resultat.biens]


def lignes_declaration(resultat) -> list[dict]:
    lignes = []
    for code in ORDRE:
        valeurs = [b.lignes[code].montant for b in resultat.biens]
        if code == "230":
            valeurs = [-v for v in valeurs]
        if code not in TOUJOURS and not any(valeurs):
            continue
        lignes.append({
            "code": code, "libelle": LIGNES[code][0], "valeurs": valeurs, "total": sum(valeurs),
            "type": "total" if code in TOTAUX else "ligne",
        })
    valeurs = [b.resultat for b in resultat.biens]
    lignes.append(
        {"code": "", "libelle": "Résultat foncier", "valeurs": valeurs, "total": sum(valeurs), "type": "resultat"}
    )
    return lignes


def detail_ligne(resultat, contexte, code: str) -> dict | None:
    if code not in ORDRE:
        return None
    montants = {o.id: o.montant for o in contexte.operations}
    operations = [
        {"texte": contexte.sources.get(i, f"Opération {i}"), "montant": montants[i]}
        for r in resultat.biens
        for i in r.lignes[code].explication.operation_ids
    ]
    libelle, regle, source = LIGNES[code]
    total = sum(r.lignes[code].montant for r in resultat.biens)
    return {"code": code, "libelle": libelle, "regle": regle, "source": source, "operations": operations, "total": total}


def cases_2042(resultat) -> list[dict]:
    return [{"code": code, "libelle": libelle, "montant": getattr(resultat.deficit, attribut)} for code, libelle, attribut in CASES]


def _arrondi(valeur: Decimal) -> int:
    return int(valeur.quantize(Decimal(1), ROUND_HALF_UP))


def estimation_impot(revenu_net: int, deficit_global: int, tmi: Decimal, taux_ps: Decimal) -> dict:
    """Impôt + prélèvements sociaux sur le revenu foncier net, économie d'impôt due au déficit (centimes)."""
    return {
        "impot": _arrondi(Decimal(revenu_net) * (tmi + taux_ps) / 100),
        "economie": _arrondi(Decimal(deficit_global) * tmi / 100),
    }


def resultat_vers_dict(resultat, contexte) -> dict:
    return {
        "annee": resultat.annee,
        "biens": [
            {"nom": nom, "lignes": {code: bien.lignes[code].montant for code in ORDRE}, "resultat": bien.resultat}
            for nom, bien in zip(colonnes_biens(resultat, contexte), resultat.biens, strict=True)
        ],
        "cases": {c["code"]: c["montant"] for c in cases_2042(resultat)},
        "deficits_apres": [[d.annee_origine, d.montant] for d in resultat.deficit.deficits_apres],
    }


def empreinte(donnees: dict) -> str:
    return hashlib.sha256(json.dumps(donnees, sort_keys=True).encode()).hexdigest()
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `177 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(declaration): mise en forme des résultats du moteur fiscal"
```

---

### Task 3: Suivi des loyers, Pinel et alertes

**Files:**
- Create: `declaration/suivi.py`
- Test: `tests/declaration/test_suivi.py`

**Interfaces:**
- Consumes: `biens.Bien` (`bail_en_cours`, `pinel`, `surface_habitable`, `surface_annexes`), `operations.Operation`, `NatureOperation`, `fiscal.pinel`, `commun.montants.format_euros`.
- Produces: `etat_loyers(bien, annee, aujourd_hui) -> list[dict]` (12 éléments : `mois`, `initiale`, `nom`, `etat` ∈ `encaisse|manquant|a_venir|sans_bail`, `libelle`) — un mois est « encaissé » s'il contient une recette ligne 211, « manquant » s'il est terminé et couvert par un bail ; `alerte_loyers(bien, etats) -> dict | None` ; `resume_pinel(bien, annee, aujourd_hui, plafonds_m2: dict) -> dict | None` (`bien`, `zone`, `reduction_annee`, `cumul`, `total`, `pourcentage`, `fin`, `loyer`, `plafond` (ou `None` si le plafond de la zone n'est pas renseigné ou s'il n'y a pas de bail), `depasse`) ; `alertes_pinel(resume, aujourd_hui) -> list[dict]`. Une alerte est un dict `{"niveau": "attention"|"info", "titre", "texte"}`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/declaration/test_suivi.py`

```python
from datetime import date

import pytest
from django.core.management import call_command

from biens.models import Bail, Bien, Locataire
from declaration.suivi import alerte_loyers, alertes_pinel, etat_loyers, resume_pinel
from tests.aides import creer_bien, creer_operation

pytestmark = pytest.mark.django_db
AUJOURD_HUI = date(2026, 10, 2)


def bien_loue():
    b = creer_bien()
    Bail.objects.create(bien=b, locataire=Locataire.objects.create(nom="L"), date_debut=date(2023, 9, 1), loyer_hc=62_000)
    return b


def test_etat_des_loyers_mois_par_mois():
    b = bien_loue()
    for mois in range(1, 9):
        creer_operation(b, "loyer", 62_000, date(2026, mois, 5))
    etats = [e["etat"] for e in etat_loyers(b, 2026, AUJOURD_HUI)]
    assert etats == ["encaisse"] * 8 + ["manquant"] + ["a_venir"] * 3


def test_mois_sans_bail():
    etats = etat_loyers(creer_bien(), 2026, AUJOURD_HUI)
    assert etats[0]["etat"] == "sans_bail"
    assert etats[0]["initiale"] == "J"


def test_alerte_loyer_manquant():
    b = bien_loue()
    etats = etat_loyers(b, 2026, AUJOURD_HUI)
    assert "septembre" in alerte_loyers(b, etats)["texte"]
    assert alerte_loyers(b, [e | {"etat": "encaisse"} for e in etats]) is None


@pytest.fixture
def t2():
    call_command("seed_demo")
    return Bien.objects.get(nom="T2 Les Tilleuls")


def test_resume_pinel_avec_plafond(t2):
    resume = resume_pinel(t2, 2025, AUJOURD_HUI, {"A": 1239})
    assert resume["reduction_annee"] == 168_000
    assert resume["pourcentage"] == 95
    assert (resume["loyer"], resume["plafond"], resume["depasse"]) == (62_000, 65_500, False)


def test_resume_pinel_sans_plafond_renseigne(t2):
    resume = resume_pinel(t2, 2025, AUJOURD_HUI, {})
    assert resume["plafond"] is None
    assert resume["depasse"] is False


def test_loyer_au_dessus_du_plafond(t2):
    Bail.objects.filter(bien=t2).update(loyer_hc=70_000)
    resume = resume_pinel(t2, 2025, AUJOURD_HUI, {"A": 1239})
    assert resume["depasse"]
    assert any("plafond" in a["titre"] for a in alertes_pinel(resume, AUJOURD_HUI))


def test_fin_d_engagement_proche(t2):
    alertes = alertes_pinel(resume_pinel(t2, 2026, AUJOURD_HUI, {}), AUJOURD_HUI)
    assert any("31/12/2026" in a["titre"] for a in alertes)
    assert resume_pinel(creer_bien("Sans Pinel"), 2026, AUJOURD_HUI, {}) is None
```

Run: `.venv/Scripts/python.exe -m pytest tests/declaration/test_suivi.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'declaration.suivi'`.

- [ ] **Step 2: Implémenter** — `declaration/suivi.py`

```python
"""Suivi de l'année : loyers mois par mois, engagement Pinel et alertes du tableau de bord."""

from datetime import date, timedelta

from commun.montants import format_euros
from fiscal.pinel import fin_engagement, plafond_loyer_mensuel, reduction_annee, reduction_cumulee, reduction_totale
from operations.models import NatureOperation, Operation

NOMS_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
LIBELLES_ETAT = {"encaisse": "encaissé", "manquant": "non saisi", "a_venir": "à venir", "sans_bail": "pas de bail"}


def _dernier_jour(annee: int, mois: int) -> date:
    return date(annee + mois // 12, mois % 12 + 1, 1) - timedelta(days=1)


def etat_loyers(bien, annee: int, aujourd_hui: date) -> list[dict]:
    encaisses = set(
        Operation.objects.filter(
            bien=bien, date_paiement__year=annee,
            categorie__nature=NatureOperation.RECETTE_IMPOSABLE, categorie__ligne_2044="211",
        ).values_list("date_paiement__month", flat=True)
    )
    etats = []
    for mois in range(1, 13):
        debut, fin = date(annee, mois, 1), _dernier_jour(annee, mois)
        if mois in encaisses:
            etat = "encaisse"
        elif fin >= aujourd_hui:
            etat = "a_venir"
        elif bien.bail_en_cours(debut) or bien.bail_en_cours(fin):
            etat = "manquant"
        else:
            etat = "sans_bail"
        nom = NOMS_MOIS[mois - 1]
        etats.append({"mois": mois, "initiale": nom[0].upper(), "nom": nom, "etat": etat, "libelle": LIBELLES_ETAT[etat]})
    return etats


def alerte_loyers(bien, etats: list[dict]) -> dict | None:
    manquants = [e["nom"] for e in etats if e["etat"] == "manquant"]
    if not manquants:
        return None
    return {
        "niveau": "attention",
        "titre": f"Loyer non saisi — {bien.nom}",
        "texte": f"Aucun loyer encaissé en {', '.join(manquants)}.",
    }


def resume_pinel(bien, annee: int, aujourd_hui: date, plafonds_m2: dict) -> dict | None:
    engagement = getattr(bien, "pinel", None)
    if engagement is None:
        return None
    e = engagement.vers_fiscal()
    total = reduction_totale(e)
    cumul = reduction_cumulee(e, annee)
    bail = bien.bail_en_cours(aujourd_hui)
    plafond_m2 = (plafonds_m2 or {}).get(engagement.zone)
    plafond = (
        plafond_loyer_mensuel(int(plafond_m2), bien.surface_habitable, bien.surface_annexes)
        if plafond_m2 and bail else None
    )
    return {
        "bien": bien,
        "zone": engagement.zone,
        "reduction_annee": reduction_annee(e, annee),
        "cumul": cumul,
        "total": total,
        "pourcentage": cumul * 100 // total if total else 0,
        "fin": fin_engagement(e),
        "loyer": bail.loyer_hc if bail else None,
        "plafond": plafond,
        "depasse": bool(plafond and bail.loyer_hc > plafond),
    }


def alertes_pinel(resume: dict, aujourd_hui: date) -> list[dict]:
    alertes = []
    nom = resume["bien"].nom
    if aujourd_hui <= resume["fin"] <= aujourd_hui + timedelta(days=365):
        alertes.append({
            "niveau": "info",
            "titre": f"Fin d'engagement Pinel le {resume['fin']:%d/%m/%Y} — {nom}",
            "texte": "Les contraintes du dispositif (plafonds de loyer et de ressources) prendront fin.",
        })
    if resume["depasse"]:
        alertes.append({
            "niveau": "attention",
            "titre": f"Loyer au-dessus du plafond Pinel — {nom}",
            "texte": f"Loyer {format_euros(resume['loyer'])} pour un plafond de {format_euros(resume['plafond'])}.",
        })
    return alertes
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `184 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(declaration): suivi des loyers, du Pinel et alertes"
```

---

### Task 4: Tableau de bord

**Files:**
- Create: `declaration/views.py`, `templates/declaration/tableau_de_bord.html`
- Modify: `config/urls.py`, `static/css/app.css`
- Delete: `commun/views.py`, `templates/accueil.html`
- Test: `tests/declaration/test_tableau_de_bord.py`

**Interfaces:**
- Consumes: Tasks 1–3 ; `calculer_annee`, `ParametresManquants`, `ParametresAnnuels` (`tmi`, `taux_prelevements_sociaux`, `plafonds_pinel_m2`), `Configuration.charger()`.
- Produces: vue `declaration.views.tableau_de_bord` à l'URL `accueil` (`/`, `?annee=` ; par défaut l'année en cours) ; helper `_annees(aujourd_hui) -> list[int]` (de l'année en cours à la première année gérée).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/declaration/test_tableau_de_bord.py`

```python
import pytest
from django.core.management import call_command

from fiscalite.models import ParametresAnnuels

pytestmark = pytest.mark.django_db


def test_tableau_de_bord_2025(client_verifie):
    call_command("seed_demo")
    contenu = client_verifie.get("/?annee=2025").content.decode()
    assert "T2 Les Tilleuls" in contenu
    assert "7\u202f440 €" in contenu
    assert "−906 €" in contenu
    assert "271,80 €" in contenu


def test_tableau_de_bord_sans_donnees(client_verifie):
    r = client_verifie.get("/")
    assert r.status_code == 200
    assert "Tableau de bord" in r.content.decode()


def test_parametres_manquants(client_verifie):
    ParametresAnnuels.objects.filter(annee=2025).delete()
    r = client_verifie.get("/?annee=2025")
    assert r.status_code == 200
    assert "Paramètres fiscaux 2025 absents" in r.content.decode()


def test_annee_anterieure_a_la_premiere_annee_geree(client_verifie):
    r = client_verifie.get("/?annee=2020")
    assert r.status_code == 200
    assert "première année" in r.content.decode()
```

(271,80 € = économie d'impôt estimée : 906 € de déficit × TMI 30 %.)

Run: `.venv/Scripts/python.exe -m pytest tests/declaration/test_tableau_de_bord.py -q`
Expected: FAIL (`T2 Les Tilleuls` absent de l'ancienne page d'accueil).

- [ ] **Step 2: Vue** — `declaration/views.py`

```python
from datetime import date

from django.shortcuts import render

from biens.models import Bien
from commun.annees import annee_demandee
from fiscalite.models import Configuration, ParametresAnnuels
from fiscalite.services import ParametresManquants, calculer_annee

from .presentation import estimation_impot
from .suivi import alerte_loyers, alertes_pinel, etat_loyers, resume_pinel


def _annees(aujourd_hui: date) -> list[int]:
    premiere = Configuration.charger().premiere_annee
    return list(range(aujourd_hui.year, min(premiere, aujourd_hui.year) - 1, -1))


def tableau_de_bord(request):
    aujourd_hui = date.today()
    annee = annee_demandee(request, aujourd_hui.year)
    contexte = {
        "annee": annee, "annees": _annees(aujourd_hui), "aujourd_hui": aujourd_hui, "annee_courante": aujourd_hui.year,
    }
    try:
        resultat, _ = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        return render(request, "declaration/tableau_de_bord.html", {**contexte, "erreur": str(erreur)})
    parametres = ParametresAnnuels.objects.get(annee=annee)
    biens = {b.pk: b for b in Bien.objects.select_related("pinel")}
    cartes, alertes, pinels = [], [], []
    for r in resultat.biens:
        bien = biens[r.bien_id]
        loyers = etat_loyers(bien, annee, aujourd_hui)
        cartes.append({
            "bien": bien, "recettes": r.recettes, "frais": r.frais, "interets": r.interets,
            "resultat": r.resultat, "loyers": loyers,
        })
        alerte = alerte_loyers(bien, loyers)
        if alerte:
            alertes.append(alerte)
        resume = resume_pinel(bien, annee, aujourd_hui, parametres.plafonds_pinel_m2)
        if resume:
            pinels.append(resume)
            alertes.extend(alertes_pinel(resume, aujourd_hui))
    alertes.extend({"niveau": "info", "titre": "Déficit foncier", "texte": texte} for texte in resultat.alertes)
    estimation = estimation_impot(
        resultat.deficit.revenu_net_estime, resultat.deficit.case_4bc, parametres.tmi,
        parametres.taux_prelevements_sociaux,
    )
    return render(request, "declaration/tableau_de_bord.html", {
        **contexte, "resultat": resultat, "parametres": parametres, "cartes": cartes, "alertes": alertes,
        "pinels": pinels, "estimation": estimation,
    })
```

Dans `config/urls.py`, remplacer `from commun.views import accueil` par `from declaration.views import tableau_de_bord` et la route `path("", accueil, name="accueil"),` par `path("", tableau_de_bord, name="accueil"),`. Supprimer `commun/views.py` et `templates/accueil.html` (`git rm`).

- [ ] **Step 3: Gabarit et styles**

`templates/declaration/tableau_de_bord.html` :

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Tableau de bord{% endblock %}
{% block contenu %}
<header class="entete">
  <div>
    <h1>Tableau de bord</h1>
    <p class="sous-titre">Année {{ annee }}{% if annee == annee_courante %} en cours — chiffres provisoires au {{ aujourd_hui|date:"d/m/Y" }}{% endif %}</p>
  </div>
  <div class="actions no-print">
    <form method="get" class="filtres">
      <div class="champ">
        <label for="annee">Année</label>
        <select id="annee" name="annee">{% for a in annees %}<option value="{{ a }}"{% if a == annee %} selected{% endif %}>{{ a }}</option>{% endfor %}</select>
      </div>
      <button class="bouton" type="submit">Afficher</button>
    </form>
    <a class="bouton principal" href="{% url 'operations:creer' %}">+ Nouvelle opération</a>
  </div>
</header>
{% if erreur %}
<div class="alerte attention" role="alert"><div><strong>Calcul impossible pour {{ annee }}</strong><span class="helptext">{{ erreur }}</span></div></div>
{% else %}
<div class="kpis">
  <div class="carte"><span class="sous-titre">Loyers et recettes</span><strong class="chiffre">{{ resultat.total_recettes|euros }}</strong><span class="helptext">Ligne 215 · {{ cartes|length }} bien{{ cartes|length|pluralize }}</span></div>
  <div class="carte"><span class="sous-titre">Charges déductibles</span><strong class="chiffre">{{ resultat.total_frais|euros }}</strong><span class="helptext">Ligne 240</span></div>
  <div class="carte"><span class="sous-titre">Intérêts d'emprunt</span><strong class="chiffre">{{ resultat.total_interets|euros }}</strong><span class="helptext">Ligne 250</span></div>
  <div class="carte">
    <span class="sous-titre">Résultat foncier</span>
    <strong class="chiffre{% if resultat.resultat_global < 0 %} negatif{% endif %}">{{ resultat.resultat_global|euros }}</strong>
    <span class="helptext">{% if estimation.economie %}Économie d'impôt estimée ≈ {{ estimation.economie|euros }} (TMI {{ parametres.tmi }} %){% else %}Impôt estimé ≈ {{ estimation.impot|euros }} (TMI {{ parametres.tmi }} % + prélèvements sociaux {{ parametres.taux_prelevements_sociaux }} %){% endif %}</span>
  </div>
</div>
<div class="grille">
  {% for c in cartes %}
  <section class="carte pile">
    <div class="ligne-resume"><div><h2>{{ c.bien.nom }}</h2><span class="helptext">{{ c.bien.get_regime_display }}</span></div>{% if c.bien.pinel %}<span class="badge accent">Pinel</span>{% endif %}</div>
    <div class="ligne-resume"><span>Recettes</span><strong>{{ c.recettes|euros }}</strong></div>
    <div class="ligne-resume"><span>Charges déductibles</span><strong>{{ c.frais|euros }}</strong></div>
    <div class="ligne-resume"><span>Intérêts d'emprunt</span><strong>{{ c.interets|euros }}</strong></div>
    <div class="ligne-resume total"><span>Résultat</span><strong{% if c.resultat < 0 %} class="negatif"{% endif %}>{{ c.resultat|euros }}</strong></div>
    <span class="helptext">Loyers encaissés en {{ annee }}</span>
    <div class="lignes-mois">
      {% for m in c.loyers %}<div class="mois {{ m.etat }}" title="{{ m.nom }} : {{ m.libelle }}"><i aria-hidden="true"></i><span>{{ m.initiale }}</span><span class="sr">{{ m.nom }} : {{ m.libelle }}</span></div>{% endfor %}
    </div>
  </section>
  {% empty %}
  <section class="carte"><p>Aucun bien pour l'instant. <a href="{% url 'biens:creer' %}">Ajouter un bien</a>.</p></section>
  {% endfor %}
</div>
<div class="grille">
  <section class="carte pile">
    <h2>À surveiller</h2>
    {% for a in alertes %}<div class="alerte {{ a.niveau }}"><div><strong>{{ a.titre }}</strong><span class="helptext">{{ a.texte }}</span></div></div>{% empty %}<p>Rien à signaler.</p>{% endfor %}
  </section>
  {% for p in pinels %}
  <section class="carte pile">
    <div class="ligne-resume"><h2>Pinel — {{ p.bien.nom }}</h2><span class="helptext">Fin d'engagement : {{ p.fin|date:"d/m/Y" }}</span></div>
    <div class="ligne-resume"><span class="helptext">Réduction obtenue</span><strong>{{ p.cumul|euros }} sur {{ p.total|euros }}</strong></div>
    <div class="barre" role="img" aria-label="{{ p.pourcentage }} % de la réduction obtenue"><span style="width: {{ p.pourcentage }}%"></span></div>
    <div class="ligne-resume"><span>Réduction {{ annee }}</span><strong>{{ p.reduction_annee|euros }}</strong></div>
    {% if p.plafond %}
    <div class="alerte {% if p.depasse %}attention{% else %}ok{% endif %}"><div><strong>Loyer {{ p.loyer|euros }} {% if p.depasse %}&gt;{% else %}≤{% endif %} plafond {{ p.plafond|euros }}</strong><span class="helptext">Zone {{ p.zone }}</span></div></div>
    {% else %}
    <p class="helptext">Plafond de loyer de la zone {{ p.zone }} non renseigné dans les paramètres {{ annee }}.</p>
    {% endif %}
  </section>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

Ajouter à la fin de `static/css/app.css` :

```css
:root{--attention:#B4410C;--attention-fond:#FBEEDC}
@media (prefers-color-scheme:dark){:root{--attention:#F0A36B;--attention-fond:#3A2A16}}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.pile{display:flex;flex-direction:column;gap:12px}
.ligne-resume{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.ligne-resume h2{margin:0}
.ligne-resume.total{padding-top:8px;border-top:1px solid var(--ligne)}
.lignes-mois{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:4px}
.mois{display:flex;flex-direction:column;align-items:center;gap:4px;font-size:11px;color:var(--attenue)}
.mois i{display:block;width:100%;height:10px;border-radius:3px;border:1px solid var(--ligne)}
.mois.encaisse i{background:var(--accent);border-color:var(--accent)}
.mois.manquant i{background:var(--attention);border-color:var(--attention)}
.alerte{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px;border-radius:10px;background:var(--ri-fond)}
.alerte strong{display:block}
.alerte.attention{background:var(--attention-fond)}
.alerte.ok{background:var(--d-fond)}
.barre{height:10px;border-radius:999px;background:var(--ligne);overflow:hidden}
.barre span{display:block;height:100%;background:var(--accent)}
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `188 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(declaration): tableau de bord chiffré"
```

---

### Task 5: Export CSV de la déclaration

**Files:**
- Create: `declaration/urls.py`
- Modify: `declaration/presentation.py`, `declaration/views.py`, `config/urls.py` (`path("declaration/", include("declaration.urls")),` après `fiscalite/`)
- Test: `tests/declaration/test_export.py`

**Interfaces:**
- Consumes: Task 2 (`lignes_declaration`, `cases_2042`, `colonnes_biens`), `fiscal.en_euros`.
- Produces: `ecrire_csv(fichier, resultat, contexte)` (séparateur `;`, euros arrondis) ; URL `declaration:export_csv` (`/declaration/<annee>/csv/`, fichier `declaration-2044-<annee>.csv`, UTF-8 avec BOM pour Excel).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/declaration/test_export.py`

```python
import pytest
from django.core.management import call_command
from django.urls import reverse

from fiscalite.models import ParametresAnnuels

pytestmark = pytest.mark.django_db


def test_export_csv(client_verifie):
    call_command("seed_demo")
    r = client_verifie.get(reverse("declaration:export_csv", args=[2025]))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/csv")
    assert "declaration-2044-2025.csv" in r["Content-Disposition"]
    lignes = r.content.decode("utf-8-sig").splitlines()
    assert lignes[0] == "Ligne;Libellé;T2 Les Tilleuls;T3 Centre;Total"
    assert "211;Loyers bruts encaissés;7440;9360;16800" in lignes
    assert ";Résultat foncier;3009;-3915;-906" in lignes
    assert "4BC;Déficit imputable sur le revenu global;906" in lignes


def test_export_sans_parametres(client_verifie):
    ParametresAnnuels.objects.filter(annee=2025).delete()
    assert client_verifie.get(reverse("declaration:export_csv", args=[2025])).status_code == 404
```

Run: `.venv/Scripts/python.exe -m pytest tests/declaration/test_export.py -q`
Expected: FAIL (`NoReverseMatch: 'declaration' is not a registered namespace`).

- [ ] **Step 2: Implémenter**

Ajouter à `declaration/presentation.py` (imports `import csv` et `from fiscal import en_euros` en tête) :

```python
def ecrire_csv(fichier, resultat, contexte) -> None:
    ecrivain = csv.writer(fichier, delimiter=";")
    ecrivain.writerow(["Ligne", "Libellé", *colonnes_biens(resultat, contexte), "Total"])
    for ligne in lignes_declaration(resultat):
        ecrivain.writerow(
            [ligne["code"], ligne["libelle"], *(en_euros(v) for v in ligne["valeurs"]), en_euros(ligne["total"])]
        )
    ecrivain.writerow([])
    ecrivain.writerow(["Case", "Libellé", "Montant"])
    for case in cases_2042(resultat):
        ecrivain.writerow([case["code"], case["libelle"], en_euros(case["montant"])])
```

Ajouter à `declaration/views.py` (imports : `from django.http import Http404, HttpResponse` ; `ecrire_csv` depuis `.presentation`) :

```python
def export_csv(request, annee):
    try:
        resultat, contexte = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        raise Http404(str(erreur)) from None
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="declaration-2044-{annee}.csv"'
    reponse.write("\ufeff")
    ecrire_csv(reponse, resultat, contexte)
    return reponse
```

`declaration/urls.py` :

```python
from django.urls import path

from . import views

app_name = "declaration"

urlpatterns = [
    path("<int:annee>/csv/", views.export_csv, name="export_csv"),
]
```

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `190 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(declaration): export CSV de la 2044"
```

---

### Task 6: Écran Déclaration

**Files:**
- Create: `templates/declaration/declaration.html`
- Modify: `declaration/views.py`, `declaration/urls.py`, `commun/context_processors.py`, `static/css/app.css`
- Test: `tests/declaration/test_declaration.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 5 ; `Bien.pinel`, `fiscal.pinel.reduction_annee`.
- Produces: URL `declaration:declaration` (`/declaration/`, `?annee=` par défaut l'année précédente, `?ligne=<code>` pour le détail) ; entrée de menu « Déclaration » ; gabarit contenant les ancres `{# actions-figer #}` et `{# alerte-modifiee #}` remplacées en Task 7.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/declaration/test_declaration.py`

```python
import pytest
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db
URL = "/declaration/"


@pytest.fixture
def demo():
    call_command("seed_demo")


def test_declaration_2025(client_verifie, demo):
    contenu = client_verifie.get(URL + "?annee=2025").content.decode()
    assert "Déclaration 2025" in contenu
    assert "T3 Centre" in contenu
    assert "Case 4BC" in contenu
    assert "906 €" in contenu
    assert reverse("declaration:export_csv", args=[2025]) in contenu
    assert ">Déclaration</a>" in contenu


def test_detail_d_une_ligne(client_verifie, demo):
    contenu = client_verifie.get(URL + "?annee=2025&ligne=224").content.decode()
    assert "Rénovation de la salle d" in contenu
    assert "agrandissement" in contenu


def test_ligne_inconnue_ignoree(client_verifie, demo):
    r = client_verifie.get(URL + "?annee=2025&ligne=abc")
    assert r.status_code == 200
    assert 'id="detail"' not in r.content.decode()


def test_annee_par_defaut(client_verifie):
    assert client_verifie.get(URL).status_code == 200


def test_reduction_pinel_de_l_annee(client_verifie, demo):
    assert "1\u202f680 €" in client_verifie.get(URL + "?annee=2025").content.decode()
```

Run: `.venv/Scripts/python.exe -m pytest tests/declaration/test_declaration.py -q`
Expected: FAIL (404 sur `/declaration/`).

- [ ] **Step 2: Vue, route, menu**

Ajouter à `declaration/views.py` (imports : `from fiscal.pinel import reduction_annee` ; `cases_2042`, `colonnes_biens`, `detail_ligne`, `lignes_declaration` depuis `.presentation`) :

```python
def declaration(request):
    aujourd_hui = date.today()
    annee = annee_demandee(request, aujourd_hui.year - 1)
    contexte = {"annee": annee, "annees": _annees(aujourd_hui)}
    try:
        resultat, contexte_fiscal = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        return render(request, "declaration/declaration.html", {**contexte, "erreur": str(erreur)})
    ligne_choisie = request.GET.get("ligne", "")
    pinel = [
        {"bien": bien.nom, "reduction": reduction_annee(bien.pinel.vers_fiscal(), annee)}
        for bien in Bien.objects.filter(pinel__isnull=False).select_related("pinel")
    ]
    contexte.update(
        resultat=resultat,
        colonnes=colonnes_biens(resultat, contexte_fiscal),
        lignes=lignes_declaration(resultat),
        ligne_choisie=ligne_choisie,
        detail=detail_ligne(resultat, contexte_fiscal, ligne_choisie),
        cases=cases_2042(resultat),
        pinel=[p for p in pinel if p["reduction"]],
    )
    return render(request, "declaration/declaration.html", contexte)
```

Dans `declaration/urls.py`, ajouter `path("", views.declaration, name="declaration"),` en tête de `urlpatterns`. Dans `commun/context_processors.py`, insérer `("declaration:declaration", "Déclaration"),` dans `ENTREES` juste avant `("admin:index", "Paramètres"),`.

- [ ] **Step 3: Gabarit et styles** — `templates/declaration/declaration.html`

```html
{% extends "base.html" %}{% load montants %}
{% block titre %}Déclaration {{ annee }}{% endblock %}
{% block contenu %}
<header class="entete">
  <div>
    <div class="actions"><h1>Déclaration {{ annee }}</h1>{% if figee %}<span class="badge accent">Figée le {{ figee.figee_le|date:"d/m/Y" }}</span>{% endif %}</div>
    <p class="sous-titre">Formulaire 2044 — revenus fonciers, régime réel. Cliquez sur une ligne pour voir son détail. Montants arrondis à l'euro.</p>
  </div>
  <div class="actions no-print">
    <form method="get" class="filtres">
      <div class="champ">
        <label for="annee">Année</label>
        <select id="annee" name="annee">{% for a in annees %}<option value="{{ a }}"{% if a == annee %} selected{% endif %}>{{ a }}</option>{% endfor %}</select>
      </div>
      <button class="bouton" type="submit">Afficher</button>
    </form>
    {% if not erreur %}
    <a class="bouton" href="{% url 'declaration:export_csv' annee %}">Exporter CSV</a>
    <button class="bouton" type="button" onclick="window.print()">Imprimer / PDF</button>
    {# actions-figer #}
    {% endif %}
  </div>
</header>
{% if erreur %}
<div class="alerte attention" role="alert"><div><strong>Calcul impossible pour {{ annee }}</strong><span class="helptext">{{ erreur }}</span></div></div>
{% else %}
{# alerte-modifiee #}
<div class="decl">
  <div class="carte tableau">
    <table>
      <thead><tr><th>Ligne</th><th>Libellé</th>{% for nom in colonnes %}<th class="montant">{{ nom }}</th>{% endfor %}<th class="montant">Total</th></tr></thead>
      <tbody>
      {% for l in lignes %}
        <tr class="{{ l.type }}{% if l.code and l.code == ligne_choisie %} actif{% endif %}">
          <td>{{ l.code }}</td>
          <td>{% if l.code %}<a href="?annee={{ annee }}&amp;ligne={{ l.code }}#detail">{{ l.libelle }}</a>{% else %}{{ l.libelle }}{% endif %}</td>
          {% for v in l.valeurs %}<td class="montant{% if v < 0 %} negatif{% endif %}">{{ v|euros_entiers }}</td>{% endfor %}
          <td class="montant{% if l.total < 0 %} negatif{% endif %}">{{ l.total|euros_entiers }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  <div class="pile">
    {% if detail %}
    <section class="carte pile" id="detail">
      <span class="helptext">Détail — ligne {{ detail.code }}</span>
      <h2>{{ detail.libelle }}</h2>
      <p>{{ detail.regle }}</p>
      {% for o in detail.operations %}<div class="ligne-resume detail-op"><span>{{ o.texte }}</span><strong>{{ o.montant|euros }}</strong></div>{% empty %}<p class="helptext">Montant calculé automatiquement.</p>{% endfor %}
      <div class="ligne-resume total"><span>Total</span><strong>{{ detail.total|euros }}</strong></div>
      <span class="helptext">Source : {{ detail.source }}</span>
    </section>
    {% endif %}
    <section class="carte pile">
      <h2>À reporter sur la 2042</h2>
      <div class="cases">
        {% for c in cases %}<div class="case{% if c.montant %} remplie{% endif %}"><strong>Case {{ c.code }}</strong><span class="chiffre">{{ c.montant|euros_entiers }}</span><span class="helptext">{{ c.libelle }}</span></div>{% endfor %}
      </div>
      {% for a in resultat.alertes %}<p class="helptext">{{ a }}</p>{% endfor %}
      {% for p in pinel %}<div class="alerte ok"><div><strong>Réduction Pinel (2042-RICI) — {{ p.bien }}</strong></div><strong>{{ p.reduction|euros }}</strong></div>{% endfor %}
    </section>
    <section class="carte pile">
      <h2>Déficits à reporter après {{ annee }}</h2>
      {% if resultat.deficit.imputations %}<p class="helptext">Imputés cette année : {% for d in resultat.deficit.imputations %}{{ d.annee_origine }} ({{ d.montant|euros_entiers }}){% if not forloop.last %}, {% endif %}{% endfor %}</p>{% endif %}
      <table>
        <thead><tr><th>Origine</th><th class="montant">Restant</th><th>Dernière année</th></tr></thead>
        <tbody>{% for d in resultat.deficit.deficits_apres %}<tr><td>{{ d.annee_origine }}</td><td class="montant">{{ d.montant|euros_entiers }}</td><td>{{ d.annee_origine|add:10 }}</td></tr>{% empty %}<tr><td colspan="3">Aucun déficit à reporter.</td></tr>{% endfor %}</tbody>
      </table>
      {% for d in resultat.deficit.deficits_expires %}<p class="helptext negatif">Déficit {{ d.annee_origine }} expiré : {{ d.montant|euros_entiers }} perdus.</p>{% endfor %}
    </section>
  </div>
</div>
{% endif %}
{% endblock %}
```

Ajouter à la fin de `static/css/app.css` :

```css
.decl{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:16px;align-items:start}
tr.total td{font-weight:700;background:var(--fond)}
tr.resultat td{font-weight:700;border-top:2px solid var(--ligne)}
tr.actif td{background:var(--accent-doux)}
.detail-op{padding:8px 10px;border-radius:8px;background:var(--fond);font-size:14px}
.cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.case{display:flex;flex-direction:column;gap:2px;border:1px solid var(--ligne);border-radius:10px;padding:12px}
.case.remplie{border-color:var(--accent);background:var(--accent-doux)}
@media (max-width:900px){.decl{grid-template-columns:1fr}}
@media print{.side,.no-print,.messages{display:none!important}.shell{display:block}.main{padding:0}body{background:#FFFFFF;color:#000000}.carte{border-color:#999999;break-inside:avoid}a{color:inherit;text-decoration:none}}
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `195 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(declaration): écran Déclaration 2044 avec détail des lignes"
```

---

### Task 7: Déclaration figée

**Files:**
- Create: `declaration/models.py`, `declaration/migrations/0001_initial.py` (générée)
- Modify: `declaration/views.py`, `declaration/urls.py`, `templates/declaration/declaration.html`
- Test: `tests/declaration/test_figee.py`

**Interfaces:**
- Consumes: Task 2 (`resultat_vers_dict`, `empreinte`), Task 6 (vue et gabarit, ancres).
- Produces: modèle `DeclarationFigee` (`annee` unique, `figee_le` (mise à jour à chaque gel), `donnees` JSON, `empreinte`) ; URLs `declaration:figer` et `declaration:defiger` (`/declaration/<annee>/figer/`, `/declaration/<annee>/defiger/`, POST uniquement) ; contexte de l'écran Déclaration enrichi de `figee` et `modifiee`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/declaration/test_figee.py`

```python
from datetime import date

import pytest
from django.core.management import call_command
from django.urls import reverse

from declaration.models import DeclarationFigee
from tests.aides import creer_operation
from biens.models import Bien

pytestmark = pytest.mark.django_db
PAGE = "/declaration/?annee=2025"


@pytest.fixture
def demo():
    call_command("seed_demo")


def test_figer_la_declaration(client_verifie, demo):
    r = client_verifie.post(reverse("declaration:figer", args=[2025]))
    assert r.status_code == 302
    assert DeclarationFigee.objects.get(annee=2025).donnees["cases"]["4BC"] == 90_600
    contenu = client_verifie.get(PAGE).content.decode()
    assert "Figée le" in contenu
    assert "ont changé" not in contenu
    assert "window.print()" in contenu


def test_figer_uniquement_en_post(client_verifie, demo):
    assert client_verifie.get(reverse("declaration:figer", args=[2025])).status_code == 405


def test_modification_apres_gel_signalee(client_verifie, demo):
    client_verifie.post(reverse("declaration:figer", args=[2025]))
    creer_operation(Bien.objects.get(nom="T3 Centre"), "travaux", 10_000, date(2025, 11, 2), "Peinture")
    assert "ont changé" in client_verifie.get(PAGE).content.decode()


def test_defiger(client_verifie, demo):
    client_verifie.post(reverse("declaration:figer", args=[2025]))
    client_verifie.post(reverse("declaration:defiger", args=[2025]))
    assert not DeclarationFigee.objects.exists()
```

Run: `.venv/Scripts/python.exe -m pytest tests/declaration/test_figee.py -q`
Expected: FAIL — `ImportError: cannot import name 'DeclarationFigee'`.

- [ ] **Step 2: Modèle et migration** — `declaration/models.py`

```python
from django.db import models


class DeclarationFigee(models.Model):
    annee = models.PositiveSmallIntegerField("année", unique=True)
    figee_le = models.DateTimeField("figée le", auto_now=True)
    donnees = models.JSONField("résultat figé")
    empreinte = models.CharField("empreinte", max_length=64)

    class Meta:
        ordering = ["-annee"]
        verbose_name = "déclaration figée"

    def __str__(self):
        return f"Déclaration {self.annee} figée"
```

Run: `DJANGO_DEBUG=1 .venv/Scripts/python.exe manage.py makemigrations declaration`
Expected: `Migrations for 'declaration': declaration/migrations/0001_initial.py`

- [ ] **Step 3: Vues, routes, gabarit**

Dans `declaration/views.py` : imports `from django.contrib import messages`, `from django.shortcuts import redirect` (avec `render`), `from django.urls import reverse`, `from django.views.decorators.http import require_POST`, `from .models import DeclarationFigee`, et `empreinte`, `resultat_vers_dict` depuis `.presentation`. Dans la vue `declaration`, juste avant `return render(request, "declaration/declaration.html", contexte)` (le dernier), insérer :

```python
    figee = DeclarationFigee.objects.filter(annee=annee).first()
    actuelle = empreinte(resultat_vers_dict(resultat, contexte_fiscal))
    contexte.update(figee=figee, modifiee=bool(figee and figee.empreinte != actuelle))
```

Ajouter les vues :

```python
@require_POST
def figer(request, annee):
    try:
        resultat, contexte_fiscal = calculer_annee(annee)
    except (ParametresManquants, ValueError) as erreur:
        raise Http404(str(erreur)) from None
    donnees = resultat_vers_dict(resultat, contexte_fiscal)
    DeclarationFigee.objects.update_or_create(
        annee=annee, defaults={"donnees": donnees, "empreinte": empreinte(donnees)}
    )
    messages.success(request, f"Déclaration {annee} figée : elle sert de référence pour ce qui a été déclaré.")
    return redirect(f"{reverse('declaration:declaration')}?annee={annee}")


@require_POST
def defiger(request, annee):
    DeclarationFigee.objects.filter(annee=annee).delete()
    messages.success(request, f"Déclaration {annee} défigée.")
    return redirect(f"{reverse('declaration:declaration')}?annee={annee}")
```

Dans `declaration/urls.py`, ajouter :

```python
    path("<int:annee>/figer/", views.figer, name="figer"),
    path("<int:annee>/defiger/", views.defiger, name="defiger"),
```

Dans `templates/declaration/declaration.html`, remplacer `{# actions-figer #}` par :

```html
    {% if figee %}
    <form method="post" action="{% url 'declaration:defiger' annee %}">{% csrf_token %}<button class="bouton" type="submit">Défiger</button></form>
    {% else %}
    <form method="post" action="{% url 'declaration:figer' annee %}">{% csrf_token %}<button class="bouton principal" type="submit">Figer la déclaration</button></form>
    {% endif %}
```

et `{# alerte-modifiee #}` par :

```html
{% if modifiee %}
<div class="alerte attention" role="alert">
  <div>
    <strong>Des données de {{ annee }} ont changé depuis que la déclaration a été figée le {{ figee.figee_le|date:"d/m/Y" }}.</strong>
    <span class="helptext">Cases figées : {% for code, montant in figee.donnees.cases.items %}{{ code }} {{ montant|euros_entiers }}{% if not forloop.last %} · {% endif %}{% endfor %}. Vérifiez puis figez à nouveau si la déclaration a été corrigée.</span>
  </div>
  <form method="post" action="{% url 'declaration:figer' annee %}" class="no-print">{% csrf_token %}<button class="bouton" type="submit">Figer à nouveau</button></form>
</div>
{% endif %}
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `199 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(declaration): déclaration figée et alerte de modification"
```

---

### Task 8: Saisie manuelle des échéances

**Files:**
- Modify: `credit/forms.py`, `credit/views.py`, `credit/urls.py`, `templates/credit/detail.html`
- Test: `tests/credit/test_echeances.py`

**Interfaces:**
- Consumes: `credit.models.Pret`, `Echeance` ; `MontantField` ; `commun/formulaire.html` (`titre`, `intro`, `retour`, `suppression`).
- Produces: `EcheanceForm(*args, pret, **kwargs)` (refuse une date déjà occupée pour ce prêt) ; URLs `credit:ajouter_echeance` (`/credit/<pk>/echeances/nouvelle/`), `credit:modifier_echeance` (`/credit/<pk>/echeances/<echeance_pk>/`), `credit:supprimer_echeance` (`…/supprimer/`, POST).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/credit/test_echeances.py`

```python
from datetime import date

import pytest
from django.urls import reverse

from credit.models import Echeance, Pret
from tests.aides import creer_bien

pytestmark = pytest.mark.django_db


@pytest.fixture
def pret():
    return Pret.objects.create(bien=creer_bien(), banque="Banque", capital_emprunte=1, date_debut=date(2015, 1, 5))


def donnees(**kw):
    d = {"date": "2025-03-05", "capital": "612,45", "interets": "173,20", "assurance": "", "frais": "15"}
    d.update(kw)
    return d


def test_ajout_manuel(client_verifie, pret):
    r = client_verifie.post(reverse("credit:ajouter_echeance", args=[pret.pk]), donnees())
    assert r.status_code == 302
    e = Echeance.objects.get()
    assert (e.capital, e.interets, e.assurance, e.frais) == (61_245, 17_320, 0, 1_500)


def test_date_deja_occupee(client_verifie, pret):
    Echeance.objects.create(pret=pret, date=date(2025, 3, 5), interets=1)
    r = client_verifie.post(reverse("credit:ajouter_echeance", args=[pret.pk]), donnees())
    assert r.status_code == 200
    assert "existe déjà" in r.content.decode()
    assert Echeance.objects.count() == 1


def test_modification(client_verifie, pret):
    e = Echeance.objects.create(pret=pret, date=date(2025, 3, 5), interets=1)
    url = reverse("credit:modifier_echeance", args=[pret.pk, e.pk])
    assert client_verifie.post(url, donnees(interets="200")).status_code == 302
    e.refresh_from_db()
    assert e.interets == 20_000


def test_suppression(client_verifie, pret):
    e = Echeance.objects.create(pret=pret, date=date(2025, 3, 5), interets=1)
    client_verifie.post(reverse("credit:supprimer_echeance", args=[pret.pk, e.pk]))
    assert not Echeance.objects.exists()
```

Run: `.venv/Scripts/python.exe -m pytest tests/credit/test_echeances.py -q`
Expected: FAIL (`NoReverseMatch: Reverse for 'ajouter_echeance' not found`).

- [ ] **Step 2: Formulaire, vues, routes**

Ajouter à `credit/forms.py` (import `Echeance` depuis `.models`) :

```python
class EcheanceForm(forms.ModelForm):
    capital = MontantField(label="Capital remboursé (€)", required=False, minimum=0, valeur_si_vide=0)
    interets = MontantField(label="Intérêts (€)", required=False, minimum=0, valeur_si_vide=0)
    assurance = MontantField(label="Assurance emprunteur (€)", required=False, minimum=0, valeur_si_vide=0)
    frais = MontantField(label="Frais (€)", required=False, minimum=0, valeur_si_vide=0)

    class Meta:
        model = Echeance
        fields = ["date", "capital", "interets", "assurance", "frais"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, pret, **kwargs):
        super().__init__(*args, **kwargs)
        self.pret = pret

    def clean_date(self):
        jour = self.cleaned_data["date"]
        if Echeance.objects.filter(pret=self.pret, date=jour).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Une échéance existe déjà à cette date pour ce prêt.")
        return jour
```

Ajouter à `credit/views.py` (imports : `EcheanceForm` depuis `.forms`, `from django.views.decorators.http import require_POST`) :

```python
def ajouter_echeance(request, pk):
    pret = get_object_or_404(Pret, pk=pk)
    return _formulaire_echeance(request, pret, Echeance(pret=pret))


def modifier_echeance(request, pk, echeance_pk):
    pret = get_object_or_404(Pret, pk=pk)
    return _formulaire_echeance(request, pret, get_object_or_404(Echeance, pk=echeance_pk, pret=pret))


def _formulaire_echeance(request, pret, echeance):
    form = EcheanceForm(request.POST or None, instance=echeance, pret=pret)
    if request.method == "POST" and form.is_valid():
        echeance = form.save(commit=False)
        echeance.pret = pret
        echeance.save()
        messages.success(request, f"Échéance du {echeance.date:%d/%m/%Y} enregistrée.")
        return redirect(pret)
    contexte = {
        "form": form, "titre": "Modifier l'échéance" if echeance.pk else "Nouvelle échéance",
        "intro": str(pret), "retour": pret.get_absolute_url(),
    }
    if echeance.pk:
        contexte["suppression"] = reverse("credit:supprimer_echeance", args=[pret.pk, echeance.pk])
    return render(request, "commun/formulaire.html", contexte)


@require_POST
def supprimer_echeance(request, pk, echeance_pk):
    pret = get_object_or_404(Pret, pk=pk)
    get_object_or_404(Echeance, pk=echeance_pk, pret=pret).delete()
    messages.success(request, "Échéance supprimée.")
    return redirect(pret)
```

Dans `credit/urls.py`, ajouter :

```python
    path("<int:pk>/echeances/nouvelle/", views.ajouter_echeance, name="ajouter_echeance"),
    path("<int:pk>/echeances/<int:echeance_pk>/", views.modifier_echeance, name="modifier_echeance"),
    path("<int:pk>/echeances/<int:echeance_pk>/supprimer/", views.supprimer_echeance, name="supprimer_echeance"),
```

Dans `templates/credit/detail.html` :
- dans le bloc `<div class="actions">` de l'en-tête, ajouter avant le lien « Importer un échéancier » : `<a class="bouton" href="{% url 'credit:ajouter_echeance' pret.pk %}">+ Échéance</a>` ;
- dans le tableau détaillé des échéances, ajouter un en-tête `<th><span class="sr">Actions</span></th>` et, dans chaque ligne, la cellule `<td><a href="{% url 'credit:modifier_echeance' pret.pk e.pk %}">Modifier</a></td>`.

- [ ] **Step 3: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `203 passed`, `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(credit): saisie manuelle des échéances"
```
