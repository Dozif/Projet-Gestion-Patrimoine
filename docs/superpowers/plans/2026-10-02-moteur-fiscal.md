# Moteur fiscal (plan 1/4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le paquet Python `fiscal`, autonome et testé, qui calcule la 2044 par bien, l'imputation et le report des déficits fonciers, les cases 4BA/4BB/4BC/4BD et la réduction Pinel.

**Architecture:** Paquet pur Python sans dépendance (ni Django, ni base). Entrées : dataclasses immuables (`Bien`, `Operation`, `DeficitReportable`, `ParametresAnnuels`, `EngagementPinel`). Sorties : dataclasses immuables portant pour chaque montant une `Explication` (règle, source, opérations). Un calculateur par régime fiscal, enregistré dans un registre ; v1 = `FONCIER_REEL`.

**Tech Stack:** Python ≥ 3.12 (poste : 3.14 via `py -3.14`), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-02-gestion-patrimoine-design.md` (sections 4 et 5).

**Suite (plans séparés, rédigés après celui-ci) :** 2 = application Django (modèles, saisie, 2FA) ; 3 = écrans tableau de bord / déclaration / exports ; 4 = Docker, Synology, sauvegardes, CI.

## Global Constraints

- Tous les montants sont des **entiers en centimes** (`int`) ; jamais de `float` pour l'argent. Surfaces et taux en `decimal.Decimal`.
- `fiscal/` n'importe **que la bibliothèque standard** (aucun import Django).
- Python ≥ 3.12 ; style vérifié par `ruff check .`.
- Textes destinés à l'utilisateur (messages d'erreur, règles, alertes) **en français**.
- Les opérations sont rattachées à l'année de `date_paiement` (comptabilité de caisse).
- Valeurs par défaut des paramètres annuels : plafond d'imputation sur le revenu global 1 070 000 c (10 700 €), forfait ligne 222 = 2 000 c (20 €) par local. Ce sont des défauts surchargeables, pas des constantes.
- Plafonds Pinel (constantes du dispositif) : prix de revient 30 000 000 c (300 000 €), 550 000 c (5 500 €) par m².
- Un déficit né l'année N est imputable sur les revenus fonciers des années N+1 à N+10 inclus.
- **Point à vérifier sur la notice 2044 de l'année** : 4BA = résultat foncier positif **avant** imputation des déficits antérieurs ; 4BD = total des déficits antérieurs non expirés restant à imputer (l'administration les impute). Le moteur fournit aussi `revenu_net_estime` (après imputation) pour l'estimation.

## Review Focus

- Opérations d'une autre année, d'un autre bien ou d'un bien d'un autre régime passées au moteur → ignorées (tests Task 2 et Task 4).
- Régularisation ligne 230 supérieure aux autres frais (frais négatifs) → la part de déficit « intérêts » est bornée au déficit, jamais de montant négatif (test Task 3).
- Bien sans aucune recette dans l'année (vacant) → pas de forfait 222 (test Task 2).
- Déficit expiré (origine < année − 10) exclu de 4BD et signalé ; déficit d'origine ≥ année refusé (tests Task 3).
- Montant nul ou négatif, ou ligne 2044 incompatible avec la nature (dont la ligne 222 saisie à la main) → `ValueError` explicite (test Task 1).

## File Structure

```text
.gitignore
pyproject.toml              # configuration pytest + ruff
requirements-dev.txt        # pytest, ruff
fiscal/
  __init__.py               # exports publics
  modeles.py                # Nature, Operation, Bien, DeficitReportable, ParametresAnnuels, Explication, LigneCalculee, en_euros
  calcul_2044.py            # calculer_bien() -> ResultatBien
  deficit.py                # appliquer_deficits() -> ResultatDeficit
  calculateur.py            # CalculateurFoncierReel, ResultatFoncier, calculateur_pour()
  pinel.py                  # EngagementPinel, PeriodePinel, base/réduction/plafond de loyer
tests/
  __init__.py
  fiscal/
    __init__.py
    fabrique.py             # op() : fabrique d'opérations de test
    test_modeles.py
    test_calcul_2044.py
    test_deficit.py
    test_calculateur.py
    test_pinel.py
```

Commandes (Git Bash, depuis `E:/Projet-Gestion-Patrimoine`) : `PY=.venv/Scripts/python.exe`.

---

### Task 1: Socle du projet et modèles de données

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `requirements-dev.txt`, `fiscal/__init__.py`, `fiscal/modeles.py`
- Test: `tests/__init__.py`, `tests/fiscal/__init__.py`, `tests/fiscal/test_modeles.py`

**Interfaces:**
- Produces: `Nature` (StrEnum), `Operation(id, bien_id, date_paiement, montant, nature, ligne_2044, libelle="")`, `Bien(id, nom, regime="FONCIER_REEL", nb_locaux=1)`, `DeficitReportable(annee_origine, montant)`, `ParametresAnnuels(annee, plafond_imputation_revenu_global=1_070_000, forfait_gestion_par_local=2_000)`, `Explication(regle, source, operation_ids=())`, `LigneCalculee(code, libelle, montant, explication)`, `en_euros(centimes) -> int`, constantes `LIGNES_RECETTES`, `LIGNES_FRAIS_SAISIES`, `LIGNE_FORFAIT`, `LIGNE_REGULARISATION`, `LIGNE_INTERETS`.

- [ ] **Step 1: Créer la configuration et l'environnement**

`.gitignore` :

```text
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
```

`requirements-dev.txt` :

```text
pytest>=8.3
ruff>=0.6
```

`pyproject.toml` :

```toml
[project]
name = "gestion-patrimoine"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Run: `py -3.14 -m venv .venv && .venv/Scripts/python.exe -m pip install -q -r requirements-dev.txt`
Expected: installation sans erreur.

Créer `tests/__init__.py` et `tests/fiscal/__init__.py` vides.

- [ ] **Step 2: Écrire les tests qui échouent** — `tests/fiscal/test_modeles.py`

```python
from datetime import date

import pytest

from fiscal.modeles import Nature, Operation, en_euros


def op(**kw):
    base = dict(
        id=1, bien_id=1, date_paiement=date(2025, 1, 5), montant=62000,
        nature=Nature.RECETTE_IMPOSABLE, ligne_2044="211",
    )
    base.update(kw)
    return Operation(**base)


def test_operation_valide():
    assert op().montant == 62000


@pytest.mark.parametrize("montant", [0, -100])
def test_montant_doit_etre_strictement_positif(montant):
    with pytest.raises(ValueError, match="strictement positif"):
        op(montant=montant)


def test_ligne_incompatible_avec_la_nature():
    with pytest.raises(ValueError, match="incompatible"):
        op(nature=Nature.CHARGE_DEDUCTIBLE, ligne_2044="211")


def test_forfait_222_non_saisissable():
    with pytest.raises(ValueError, match="incompatible"):
        op(nature=Nature.CHARGE_DEDUCTIBLE, ligne_2044="222")


def test_non_imposable_et_non_deductible_sans_ligne():
    assert op(nature=Nature.RECETTE_NON_IMPOSABLE, ligne_2044=None).ligne_2044 is None
    assert op(nature=Nature.CHARGE_NON_DEDUCTIBLE, ligne_2044=None).ligne_2044 is None
    with pytest.raises(ValueError, match="incompatible"):
        op(nature=Nature.RECETTE_NON_IMPOSABLE, ligne_2044="211")


def test_regularisation_et_interets():
    assert op(nature=Nature.CHARGE_DEDUCTIBLE, ligne_2044="230").ligne_2044 == "230"
    assert op(nature=Nature.INTERETS, ligne_2044="250").ligne_2044 == "250"


@pytest.mark.parametrize("centimes,euros", [(15050, 151), (15049, 150), (-15050, -151), (0, 0)])
def test_en_euros_arrondi_au_plus_proche(centimes, euros):
    assert en_euros(centimes) == euros
```

- [ ] **Step 3: Vérifier l'échec**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal/test_modeles.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscal'`.

- [ ] **Step 4: Implémenter** — `fiscal/modeles.py`

```python
"""Structures de données d'entrée et de sortie du moteur fiscal (montants en centimes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Nature(StrEnum):
    RECETTE_IMPOSABLE = "RECETTE_IMPOSABLE"
    RECETTE_NON_IMPOSABLE = "RECETTE_NON_IMPOSABLE"
    CHARGE_DEDUCTIBLE = "CHARGE_DEDUCTIBLE"
    CHARGE_NON_DEDUCTIBLE = "CHARGE_NON_DEDUCTIBLE"
    INTERETS = "INTERETS"


LIGNES_RECETTES = ("211", "212", "213", "214")
LIGNES_FRAIS_SAISIES = ("221", "223", "224", "225", "226", "227", "229")
LIGNE_FORFAIT = "222"
LIGNE_REGULARISATION = "230"
LIGNE_INTERETS = "250"

_LIGNES_PAR_NATURE: dict[Nature, tuple[str | None, ...]] = {
    Nature.RECETTE_IMPOSABLE: LIGNES_RECETTES,
    Nature.CHARGE_DEDUCTIBLE: LIGNES_FRAIS_SAISIES + (LIGNE_REGULARISATION,),
    Nature.INTERETS: (LIGNE_INTERETS,),
    Nature.RECETTE_NON_IMPOSABLE: (None,),
    Nature.CHARGE_NON_DEDUCTIBLE: (None,),
}


@dataclass(frozen=True)
class Operation:
    """Un encaissement ou un paiement. La ligne 230 (régularisation) vient en déduction des frais."""

    id: int
    bien_id: int
    date_paiement: date
    montant: int
    nature: Nature
    ligne_2044: str | None
    libelle: str = ""

    def __post_init__(self) -> None:
        if self.montant <= 0:
            raise ValueError("Le montant d'une opération doit être strictement positif (en centimes).")
        if self.ligne_2044 not in _LIGNES_PAR_NATURE[self.nature]:
            raise ValueError(
                f"Ligne 2044 {self.ligne_2044!r} incompatible avec la nature {self.nature.value}."
            )


@dataclass(frozen=True)
class Bien:
    id: int
    nom: str
    regime: str = "FONCIER_REEL"
    nb_locaux: int = 1


@dataclass(frozen=True)
class DeficitReportable:
    annee_origine: int
    montant: int


@dataclass(frozen=True)
class ParametresAnnuels:
    annee: int
    plafond_imputation_revenu_global: int = 1_070_000
    forfait_gestion_par_local: int = 2_000


@dataclass(frozen=True)
class Explication:
    regle: str
    source: str
    operation_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class LigneCalculee:
    code: str
    libelle: str
    montant: int
    explication: Explication


def en_euros(centimes: int) -> int:
    """Arrondit des centimes à l'euro le plus proche (0,50 € arrondi à l'euro supérieur)."""
    quotient, reste = divmod(abs(centimes), 100)
    euros = quotient + (1 if reste >= 50 else 0)
    return -euros if centimes < 0 else euros
```

`fiscal/__init__.py` :

```python
"""Moteur fiscal des revenus fonciers (sans dépendance externe)."""
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal/test_modeles.py -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `11 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml requirements-dev.txt fiscal tests
git commit -m "feat(fiscal): socle du projet et modèles de données"
```

---

### Task 2: Calcul de la 2044 par bien

**Files:**
- Create: `fiscal/calcul_2044.py`
- Test: `tests/fiscal/fabrique.py`, `tests/fiscal/test_calcul_2044.py`

**Interfaces:**
- Consumes: `Bien`, `Operation`, `Nature`, `ParametresAnnuels`, `Explication`, `LigneCalculee`, constantes de lignes (Task 1).
- Produces: `calculer_bien(annee: int, bien: Bien, operations: Iterable[Operation], params: ParametresAnnuels) -> ResultatBien` ; `ResultatBien(bien_id: int, lignes: dict[str, LigneCalculee], resultat: int)` avec propriétés `recettes` (ligne 215), `frais` (240), `interets` (250). Codes présents dans `lignes` : 211–215, 221–227, 229, 230, 240, 250. Test helper `op(bien_id, code, montant, *, nature=None, annee=2025, mois=1, libelle="") -> Operation`.

- [ ] **Step 1: Écrire la fabrique de test** — `tests/fiscal/fabrique.py`

```python
from datetime import date
from itertools import count

from fiscal.modeles import LIGNE_INTERETS, LIGNES_RECETTES, Nature, Operation

_ids = count(1)


def op(bien_id, code, montant, *, nature=None, annee=2025, mois=1, libelle=""):
    if nature is None:
        if code is None:
            raise ValueError("Préciser la nature d'une opération sans ligne 2044.")
        if code in LIGNES_RECETTES:
            nature = Nature.RECETTE_IMPOSABLE
        elif code == LIGNE_INTERETS:
            nature = Nature.INTERETS
        else:
            nature = Nature.CHARGE_DEDUCTIBLE
    return Operation(
        id=next(_ids), bien_id=bien_id, date_paiement=date(annee, mois, 15),
        montant=montant, nature=nature, ligne_2044=code, libelle=libelle,
    )
```

- [ ] **Step 2: Écrire les tests qui échouent** — `tests/fiscal/test_calcul_2044.py`

```python
from fiscal.calcul_2044 import calculer_bien
from fiscal.modeles import Bien, Nature, ParametresAnnuels
from tests.fiscal.fabrique import op

B = Bien(id=1, nom="T2")
P = ParametresAnnuels(annee=2025)


def test_recettes_et_total_215():
    r = calculer_bien(2025, B, [op(1, "211", 62000), op(1, "211", 62000), op(1, "214", 10000)], P)
    assert r.lignes["211"].montant == 124000
    assert r.lignes["214"].montant == 10000
    assert r.lignes["215"].montant == 134000
    assert r.recettes == 134000


def test_frais_avec_forfait_et_regularisation():
    ops = [
        op(1, "211", 744000), op(1, "221", 52100), op(1, "223", 14800),
        op(1, "227", 81200), op(1, "229", 96000), op(1, "230", 21000),
    ]
    r = calculer_bien(2025, B, ops, P)
    assert r.lignes["222"].montant == 2000
    assert r.lignes["230"].montant == 21000
    assert r.frais == 52100 + 2000 + 14800 + 81200 + 96000 - 21000


def test_interets_et_resultat():
    ops = [
        op(1, "211", 744000), op(1, "221", 52100), op(1, "223", 14800),
        op(1, "227", 81200), op(1, "229", 96000), op(1, "230", 21000), op(1, "250", 218000),
    ]
    r = calculer_bien(2025, B, ops, P)
    assert r.interets == 218000
    assert r.resultat == 300900


def test_explication_liste_les_operations():
    travaux = op(1, "224", 420000)
    r = calculer_bien(2025, B, [op(1, "211", 1000), travaux], P)
    assert r.lignes["224"].explication.operation_ids == (travaux.id,)
    assert "agrandissement" in r.lignes["224"].explication.regle


def test_ignore_autres_annees_autres_biens_et_operations_hors_2044():
    ops = [
        op(1, "211", 62000),
        op(1, "211", 62000, annee=2024),
        op(2, "211", 99900),
        op(1, None, 14000, nature=Nature.RECETTE_NON_IMPOSABLE),
        op(1, None, 61245, nature=Nature.CHARGE_NON_DEDUCTIBLE),
    ]
    r = calculer_bien(2025, B, ops, P)
    assert r.lignes["211"].montant == 62000
    assert r.frais == 2000


def test_pas_de_forfait_sans_recette():
    r = calculer_bien(2025, B, [op(1, "224", 10000)], P)
    assert r.lignes["222"].montant == 0
    assert r.resultat == -10000


def test_forfait_par_local():
    immeuble = Bien(id=1, nom="Immeuble", nb_locaux=3)
    r = calculer_bien(2025, immeuble, [op(1, "211", 100000)], P)
    assert r.lignes["222"].montant == 6000
```

- [ ] **Step 3: Vérifier l'échec**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal/test_calcul_2044.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscal.calcul_2044'`.

- [ ] **Step 4: Implémenter** — `fiscal/calcul_2044.py`

```python
"""Calcul des lignes de la déclaration 2044 pour un bien et une année."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .modeles import (
    LIGNE_FORFAIT,
    LIGNE_INTERETS,
    LIGNE_REGULARISATION,
    LIGNES_FRAIS_SAISIES,
    LIGNES_RECETTES,
    Bien,
    Explication,
    LigneCalculee,
    Nature,
    Operation,
    ParametresAnnuels,
)

NOTICE = "Notice de la déclaration 2044"

# code -> (libellé, règle, source)
LIGNES: dict[str, tuple[str, str, str]] = {
    "211": ("Loyers bruts encaissés", "Loyers hors charges réellement encaissés dans l'année.", NOTICE),
    "212": ("Dépenses du propriétaire mises à la charge du locataire",
            "Dépenses incombant normalement au propriétaire et payées par le locataire.", NOTICE),
    "213": ("Subventions et indemnités pour travaux", "Subventions ANAH et indemnités couvrant des charges déductibles.",
            NOTICE),
    "214": ("Autres recettes", "Indemnités d'assurance pour pertes de loyers et autres recettes.", NOTICE),
    "215": ("Total des recettes", "Somme des lignes 211 à 214.", NOTICE),
    "221": ("Frais d'administration et de gestion",
            "Honoraires d'agence, frais de procédure, rémunération d'un gardien : montant réel.",
            "BOFiP BOI-RFPI-BASE-20-10"),
    "222": ("Autres frais de gestion", "Forfait par local loué dans l'année (correspondance, téléphone, etc.).", NOTICE),
    "223": ("Primes d'assurance", "Assurance propriétaire non occupant, garantie des loyers impayés.", NOTICE),
    "224": ("Travaux de réparation, d'entretien et d'amélioration",
            "Déductibles sauf travaux de construction, de reconstruction ou d'agrandissement.",
            "BOFiP BOI-RFPI-BASE-20-30"),
    "225": ("Charges récupérables non récupérées",
            "Charges récupérables restées à la charge du propriétaire au départ du locataire.", NOTICE),
    "226": ("Indemnités d'éviction et frais de relogement", "Indemnités versées pour libérer le local.", NOTICE),
    "227": ("Taxes foncières", "Taxe foncière déductible, hors taxe d'enlèvement des ordures ménagères.", NOTICE),
    "229": ("Provisions pour charges de copropriété", "Provisions versées au syndic dans l'année.", NOTICE),
    "230": ("Régularisation des provisions de l'année précédente",
            "Part non déductible des provisions déduites l'année précédente, d'après le décompte du syndic : "
            "vient en diminution des frais.", NOTICE),
    "240": ("Total des frais et charges", "Lignes 221 à 229, moins la ligne 230.", NOTICE),
    "250": ("Intérêts et frais d'emprunt",
            "Intérêts, assurance emprunteur et frais d'emprunt ; le capital remboursé n'est pas déductible.",
            "BOFiP BOI-RFPI-BASE-20-80"),
}


@dataclass(frozen=True)
class ResultatBien:
    bien_id: int
    lignes: dict[str, LigneCalculee]
    resultat: int

    @property
    def recettes(self) -> int:
        return self.lignes["215"].montant

    @property
    def frais(self) -> int:
        return self.lignes["240"].montant

    @property
    def interets(self) -> int:
        return self.lignes[LIGNE_INTERETS].montant


def _ligne(code: str, montant: int, operation_ids: tuple[int, ...] = ()) -> LigneCalculee:
    libelle, regle, source = LIGNES[code]
    return LigneCalculee(code, libelle, montant, Explication(regle, source, operation_ids))


def calculer_bien(
    annee: int, bien: Bien, operations: Iterable[Operation], params: ParametresAnnuels
) -> ResultatBien:
    ops = [o for o in operations if o.bien_id == bien.id and o.date_paiement.year == annee]

    def somme(code: str, nature: Nature) -> LigneCalculee:
        retenues = [o for o in ops if o.ligne_2044 == code and o.nature == nature]
        return _ligne(code, sum(o.montant for o in retenues), tuple(o.id for o in retenues))

    lignes: dict[str, LigneCalculee] = {}
    for code in LIGNES_RECETTES:
        lignes[code] = somme(code, Nature.RECETTE_IMPOSABLE)
    lignes["215"] = _ligne("215", sum(lignes[c].montant for c in LIGNES_RECETTES))

    a_des_recettes = any(o.nature == Nature.RECETTE_IMPOSABLE for o in ops)
    forfait = params.forfait_gestion_par_local * bien.nb_locaux if a_des_recettes else 0
    lignes[LIGNE_FORFAIT] = _ligne(LIGNE_FORFAIT, forfait)
    for code in LIGNES_FRAIS_SAISIES + (LIGNE_REGULARISATION,):
        lignes[code] = somme(code, Nature.CHARGE_DEDUCTIBLE)
    frais = (
        sum(lignes[c].montant for c in LIGNES_FRAIS_SAISIES)
        + forfait
        - lignes[LIGNE_REGULARISATION].montant
    )
    lignes["240"] = _ligne("240", frais)

    lignes[LIGNE_INTERETS] = somme(LIGNE_INTERETS, Nature.INTERETS)

    resultat = lignes["215"].montant - frais - lignes[LIGNE_INTERETS].montant
    return ResultatBien(bien.id, lignes, resultat)
```

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `18 passed`, `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add fiscal/calcul_2044.py tests/fiscal/fabrique.py tests/fiscal/test_calcul_2044.py
git commit -m "feat(fiscal): calcul des lignes 2044 par bien"
```

---

### Task 3: Imputation et report des déficits

**Files:**
- Create: `fiscal/deficit.py`
- Test: `tests/fiscal/test_deficit.py`

**Interfaces:**
- Consumes: `DeficitReportable`, `ParametresAnnuels` (Task 1).
- Produces: `appliquer_deficits(annee: int, recettes: int, frais: int, interets: int, deficits_anterieurs: Iterable[DeficitReportable], params: ParametresAnnuels) -> ResultatDeficit` ; `ResultatDeficit(case_4ba, case_4bb, case_4bc, case_4bd, imputations, deficits_apres, deficits_expires, revenu_net_estime)` — les trois collections sont des `tuple[DeficitReportable, ...]` triés par année d'origine ; `imputations` donne le montant imputé par année d'origine ; `deficits_apres` est le stock à reprendre l'année suivante (y compris le déficit né dans l'année).

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/fiscal/test_deficit.py`

```python
import pytest

from fiscal.deficit import appliquer_deficits
from fiscal.modeles import DeficitReportable as DR
from fiscal.modeles import ParametresAnnuels

P = ParametresAnnuels(annee=2025)


def test_benefice_sans_deficit_anterieur():
    d = appliquer_deficits(2025, 1_000_000, 300_000, 200_000, (), P)
    assert (d.case_4ba, d.case_4bb, d.case_4bc, d.case_4bd) == (500_000, 0, 0, 0)
    assert d.revenu_net_estime == 500_000
    assert d.deficits_apres == ()


def test_benefice_impute_les_deficits_les_plus_anciens_dabord():
    d = appliquer_deficits(2025, 1_000_000, 300_000, 200_000, (DR(2023, 150_000), DR(2020, 400_000)), P)
    assert d.case_4ba == 500_000
    assert d.case_4bd == 550_000
    assert d.imputations == (DR(2020, 400_000), DR(2023, 100_000))
    assert d.deficits_apres == (DR(2023, 50_000),)
    assert d.revenu_net_estime == 0


def test_deficit_du_aux_autres_charges_impute_sur_le_revenu_global():
    d = appliquer_deficits(2025, 1_680_000, 1_157_600, 613_000, (), P)
    assert (d.case_4ba, d.case_4bb, d.case_4bc) == (0, 0, 90_600)
    assert d.deficits_apres == ()


def test_deficit_plafonne_a_10700_euros():
    d = appliquer_deficits(2025, 1_000_000, 2_500_000, 200_000, (), P)
    assert d.case_4bc == 1_070_000
    assert d.case_4bb == 630_000
    assert d.deficits_apres == (DR(2025, 630_000),)


def test_part_due_aux_interets_seulement_reportable():
    d = appliquer_deficits(2025, 300_000, 100_000, 500_000, (), P)
    assert d.case_4bc == 100_000
    assert d.case_4bb == 200_000


def test_regularisation_superieure_aux_frais_borne_la_part_interets():
    d = appliquer_deficits(2025, 100_000, -50_000, 400_000, (), P)
    assert d.case_4bc == 0
    assert d.case_4bb == 250_000


def test_deficits_anterieurs_conserves_en_annee_deficitaire():
    anterieurs = (DR(2022, 240_000), DR(2023, 115_000))
    d = appliquer_deficits(2025, 1_680_000, 1_157_600, 613_000, anterieurs, P)
    assert d.case_4bd == 355_000
    assert d.imputations == ()
    assert d.deficits_apres == anterieurs


def test_deficit_expire_exclu():
    d = appliquer_deficits(2025, 500_000, 0, 0, (DR(2014, 100_000), DR(2015, 50_000)), P)
    assert d.deficits_expires == (DR(2014, 100_000),)
    assert d.case_4bd == 50_000
    assert d.imputations == (DR(2015, 50_000),)


def test_deficit_d_origine_non_anterieure_refuse():
    with pytest.raises(ValueError, match="antérieur"):
        appliquer_deficits(2025, 500_000, 0, 0, (DR(2025, 100_000),), P)
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal/test_deficit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscal.deficit'`.

- [ ] **Step 3: Implémenter** — `fiscal/deficit.py`

```python
"""Imputation des déficits fonciers (art. 156-I-3° du CGI)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .modeles import DeficitReportable, ParametresAnnuels

DUREE_REPORT_ANS = 10


@dataclass(frozen=True)
class ResultatDeficit:
    case_4ba: int
    case_4bb: int
    case_4bc: int
    case_4bd: int
    imputations: tuple[DeficitReportable, ...]
    deficits_apres: tuple[DeficitReportable, ...]
    deficits_expires: tuple[DeficitReportable, ...]
    revenu_net_estime: int


def appliquer_deficits(
    annee: int,
    recettes: int,
    frais: int,
    interets: int,
    deficits_anterieurs: Iterable[DeficitReportable],
    params: ParametresAnnuels,
) -> ResultatDeficit:
    stock = sorted((d for d in deficits_anterieurs if d.montant > 0), key=lambda d: d.annee_origine)
    if any(d.annee_origine >= annee for d in stock):
        raise ValueError(f"Un déficit reporté doit être antérieur à {annee}.")
    expires = tuple(d for d in stock if d.annee_origine < annee - DUREE_REPORT_ANS)
    valides = tuple(d for d in stock if d.annee_origine >= annee - DUREE_REPORT_ANS)
    case_4bd = sum(d.montant for d in valides)

    resultat = recettes - frais - interets
    if resultat >= 0:
        reste = resultat
        imputations: list[DeficitReportable] = []
        apres: list[DeficitReportable] = []
        for d in valides:
            impute = min(d.montant, reste)
            reste -= impute
            if impute:
                imputations.append(DeficitReportable(d.annee_origine, impute))
            if d.montant - impute:
                apres.append(DeficitReportable(d.annee_origine, d.montant - impute))
        return ResultatDeficit(resultat, 0, 0, case_4bd, tuple(imputations), tuple(apres), expires, reste)

    deficit = -resultat
    part_interets = min(max(0, interets - recettes), deficit)
    part_autres = deficit - part_interets
    imputable_global = min(part_autres, params.plafond_imputation_revenu_global)
    reportable = deficit - imputable_global
    apres = valides + ((DeficitReportable(annee, reportable),) if reportable else ())
    return ResultatDeficit(0, reportable, imputable_global, case_4bd, (), apres, expires, 0)
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `27 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add fiscal/deficit.py tests/fiscal/test_deficit.py
git commit -m "feat(fiscal): imputation et report des déficits fonciers"
```

---

### Task 4: Calculateur « foncier réel » et registre des régimes

**Files:**
- Create: `fiscal/calculateur.py`
- Modify: `fiscal/__init__.py`
- Test: `tests/fiscal/test_calculateur.py`

**Interfaces:**
- Consumes: `calculer_bien`, `ResultatBien` (Task 2) ; `appliquer_deficits`, `ResultatDeficit` (Task 3) ; modèles (Task 1).
- Produces: `CalculateurFoncierReel().calculer(annee, biens, operations, deficits, params) -> ResultatFoncier` ; `ResultatFoncier(annee, biens: tuple[ResultatBien, ...], total_recettes, total_frais, total_interets, resultat_global, deficit: ResultatDeficit, alertes: tuple[str, ...])` ; `calculateur_pour(regime: str) -> Calculateur` (lève `NotImplementedError` pour un régime non pris en charge) ; `REGIME_FONCIER_REEL = "FONCIER_REEL"`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/fiscal/test_calculateur.py`

```python
import pytest

from fiscal.calculateur import CalculateurFoncierReel, calculateur_pour
from fiscal.modeles import Bien, ParametresAnnuels
from fiscal.modeles import DeficitReportable as DR
from tests.fiscal.fabrique import op

P = ParametresAnnuels(annee=2025)
T2 = Bien(id=1, nom="T2 Les Tilleuls")
T3 = Bien(id=2, nom="T3 Centre")


def operations_2025():
    return [
        op(1, "211", 744000), op(1, "221", 52100), op(1, "223", 14800), op(1, "227", 81200),
        op(1, "229", 96000), op(1, "230", 21000), op(1, "250", 218000),
        op(2, "211", 936000), op(2, "221", 65500), op(2, "223", 17500), op(2, "224", 640000),
        op(2, "227", 104500), op(2, "229", 132000), op(2, "230", 29000), op(2, "250", 395000),
    ]


def test_exemple_complet_deux_biens_un_deficitaire():
    anterieurs = (DR(2022, 240_000), DR(2023, 115_000))
    r = CalculateurFoncierReel().calculer(2025, [T2, T3], operations_2025(), anterieurs, P)
    assert [b.resultat for b in r.biens] == [300_900, -391_500]
    assert (r.total_recettes, r.total_frais, r.total_interets) == (1_680_000, 1_157_600, 613_000)
    assert r.resultat_global == -90_600
    assert r.deficit.case_4bc == 90_600
    assert r.deficit.case_4bb == 0
    assert r.deficit.case_4bd == 355_000
    assert any("31/12/2028" in a for a in r.alertes)


def test_biens_d_un_autre_regime_ignores():
    lmnp = Bien(id=3, nom="Studio meublé", regime="LMNP_REEL")
    ops = operations_2025() + [op(3, "211", 500000)]
    r = CalculateurFoncierReel().calculer(2025, [T2, T3, lmnp], ops, (), P)
    assert [b.bien_id for b in r.biens] == [1, 2]
    assert r.total_recettes == 1_680_000


def test_parametres_d_une_autre_annee_refuses():
    with pytest.raises(ValueError, match="2024"):
        CalculateurFoncierReel().calculer(2025, [T2], [], (), ParametresAnnuels(annee=2024))


def test_alerte_deficit_en_derniere_annee_et_deficit_expire():
    r = CalculateurFoncierReel().calculer(
        2025, [T3], [op(2, "224", 100000)], (DR(2014, 30_000), DR(2015, 50_000)), P
    )
    assert any("2015" in a and "dernière année" in a for a in r.alertes)
    assert any("2014" in a and "expiré" in a for a in r.alertes)


def test_registre_des_regimes():
    assert isinstance(calculateur_pour("FONCIER_REEL"), CalculateurFoncierReel)
    with pytest.raises(NotImplementedError, match="LMNP_REEL"):
        calculateur_pour("LMNP_REEL")
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal/test_calculateur.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscal.calculateur'`.

- [ ] **Step 3: Implémenter** — `fiscal/calculateur.py`

```python
"""Calculateurs par régime fiscal et registre des régimes pris en charge."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .calcul_2044 import ResultatBien, calculer_bien
from .deficit import DUREE_REPORT_ANS, ResultatDeficit, appliquer_deficits
from .modeles import Bien, DeficitReportable, Operation, ParametresAnnuels, en_euros

REGIME_FONCIER_REEL = "FONCIER_REEL"


@dataclass(frozen=True)
class ResultatFoncier:
    annee: int
    biens: tuple[ResultatBien, ...]
    total_recettes: int
    total_frais: int
    total_interets: int
    resultat_global: int
    deficit: ResultatDeficit
    alertes: tuple[str, ...]


class Calculateur(Protocol):
    regime: str

    def calculer(
        self,
        annee: int,
        biens: Iterable[Bien],
        operations: Iterable[Operation],
        deficits: Iterable[DeficitReportable],
        params: ParametresAnnuels,
    ) -> ResultatFoncier: ...


class CalculateurFoncierReel:
    regime = REGIME_FONCIER_REEL

    def calculer(
        self,
        annee: int,
        biens: Iterable[Bien],
        operations: Iterable[Operation],
        deficits: Iterable[DeficitReportable],
        params: ParametresAnnuels,
    ) -> ResultatFoncier:
        if params.annee != annee:
            raise ValueError(f"Paramètres de l'année {params.annee} fournis pour un calcul {annee}.")
        operations = list(operations)
        resultats = tuple(
            calculer_bien(annee, b, operations, params) for b in biens if b.regime == self.regime
        )
        recettes = sum(r.recettes for r in resultats)
        frais = sum(r.frais for r in resultats)
        interets = sum(r.interets for r in resultats)
        deficit = appliquer_deficits(annee, recettes, frais, interets, deficits, params)

        alertes: list[str] = []
        if deficit.case_4bc > 0:
            alertes.append(
                f"Déficit imputé sur le revenu global en {annee} : les biens doivent rester loués "
                f"jusqu'au 31/12/{annee + 3}."
            )
        for d in deficit.deficits_apres:
            if d.annee_origine == annee - DUREE_REPORT_ANS:
                alertes.append(
                    f"Déficit {d.annee_origine} : dernière année d'imputation, "
                    f"{en_euros(d.montant)} € seront perdus après {annee}."
                )
        for d in deficit.deficits_expires:
            alertes.append(f"Déficit {d.annee_origine} expiré : {en_euros(d.montant)} € non imputés.")

        return ResultatFoncier(
            annee, resultats, recettes, frais, interets, recettes - frais - interets, deficit, tuple(alertes)
        )


_CALCULATEURS: dict[str, Calculateur] = {REGIME_FONCIER_REEL: CalculateurFoncierReel()}


def calculateur_pour(regime: str) -> Calculateur:
    try:
        return _CALCULATEURS[regime]
    except KeyError:
        raise NotImplementedError(f"Régime fiscal non pris en charge : {regime}") from None
```

Remplacer `fiscal/__init__.py` par :

```python
"""Moteur fiscal des revenus fonciers (sans dépendance externe)."""

from .calcul_2044 import ResultatBien, calculer_bien
from .calculateur import REGIME_FONCIER_REEL, CalculateurFoncierReel, ResultatFoncier, calculateur_pour
from .deficit import ResultatDeficit, appliquer_deficits
from .modeles import (
    Bien,
    DeficitReportable,
    Explication,
    LigneCalculee,
    Nature,
    Operation,
    ParametresAnnuels,
    en_euros,
)

__all__ = [
    "REGIME_FONCIER_REEL", "Bien", "CalculateurFoncierReel", "DeficitReportable", "Explication",
    "LigneCalculee", "Nature", "Operation", "ParametresAnnuels", "ResultatBien", "ResultatDeficit",
    "ResultatFoncier", "appliquer_deficits", "calculateur_pour", "calculer_bien", "en_euros",
]
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `32 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add fiscal/calculateur.py fiscal/__init__.py tests/fiscal/test_calculateur.py
git commit -m "feat(fiscal): calculateur foncier réel et registre des régimes"
```

---

### Task 5: Pinel — réduction d'impôt et plafond de loyer

**Files:**
- Create: `fiscal/pinel.py`
- Modify: `fiscal/__init__.py`
- Test: `tests/fiscal/test_pinel.py`

**Interfaces:**
- Consumes: rien des autres tâches (module indépendant).
- Produces: `PeriodePinel(annee_debut: int, annee_fin: int, taux_annuel: Decimal)` (taux en %), `EngagementPinel(date_mise_en_location: date, duree_annees: int, prix_revient: int, surface_habitable: Decimal, periodes: tuple[PeriodePinel, ...])`, `base_reduction(e) -> int`, `reduction_annee(e, annee) -> int`, `reduction_cumulee(e, jusqu_a: int) -> int`, `reduction_totale(e) -> int`, `fin_engagement(e) -> date`, `plafond_loyer_mensuel(plafond_m2: int, surface_habitable: Decimal, surface_annexes: Decimal) -> int`.

- [ ] **Step 1: Écrire les tests qui échouent** — `tests/fiscal/test_pinel.py`

```python
from datetime import date
from decimal import Decimal as D

import pytest

from fiscal.pinel import (
    EngagementPinel,
    PeriodePinel,
    base_reduction,
    fin_engagement,
    plafond_loyer_mensuel,
    reduction_annee,
    reduction_cumulee,
    reduction_totale,
)

PERIODES = (PeriodePinel(2015, 2023, D("2")), PeriodePinel(2024, 2026, D("1")))


def engagement(prix=16_800_000, surface=D("45"), periodes=PERIODES, debut=date(2015, 1, 1), duree=12):
    return EngagementPinel(debut, duree, prix, surface, periodes)


def test_base_plafonnee_a_300000_euros():
    assert base_reduction(engagement(prix=35_000_000, surface=D("80"))) == 30_000_000


def test_base_plafonnee_a_5500_euros_le_m2():
    assert base_reduction(engagement(prix=29_000_000, surface=D("50"))) == 27_500_000


def test_reduction_annuelle_et_cumuls():
    e = engagement()
    assert reduction_annee(e, 2020) == 336_000
    assert reduction_annee(e, 2026) == 168_000
    assert reduction_annee(e, 2027) == 0
    assert reduction_cumulee(e, 2025) == 3_360_000
    assert reduction_totale(e) == 3_528_000


def test_periodes_qui_se_chevauchent_refusees():
    with pytest.raises(ValueError, match="chevauch"):
        engagement(periodes=(PeriodePinel(2015, 2023, D("2")), PeriodePinel(2023, 2026, D("1"))))


def test_duree_invalide_refusee():
    with pytest.raises(ValueError, match="6, 9 ou 12"):
        engagement(duree=10)


@pytest.mark.parametrize(
    "debut,duree,fin",
    [(date(2015, 3, 1), 12, date(2027, 2, 28)), (date(2016, 2, 29), 9, date(2025, 2, 28))],
)
def test_fin_engagement(debut, duree, fin):
    assert fin_engagement(engagement(debut=debut, duree=duree)) == fin


def test_plafond_de_loyer_avec_coefficient_arrondi():
    assert plafond_loyer_mensuel(1239, D("45"), D("7")) == 65_500


def test_coefficient_plafonne_a_1_2():
    assert plafond_loyer_mensuel(1000, D("20"), D("0")) == 24_000


def test_annexes_plafonnees_a_8_m2():
    assert plafond_loyer_mensuel(1000, D("60"), D("30")) == plafond_loyer_mensuel(1000, D("60"), D("16"))
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal/test_pinel.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fiscal.pinel'`.

- [ ] **Step 3: Implémenter** — `fiscal/pinel.py`

```python
"""Dispositif Pinel : réduction d'impôt et plafond de loyer (art. 199 novovicies du CGI)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

PLAFOND_PRIX_REVIENT = 30_000_000
PLAFOND_PAR_M2 = 550_000
DUREES_AUTORISEES = (6, 9, 12)


@dataclass(frozen=True)
class PeriodePinel:
    annee_debut: int
    annee_fin: int
    taux_annuel: Decimal


@dataclass(frozen=True)
class EngagementPinel:
    date_mise_en_location: date
    duree_annees: int
    prix_revient: int
    surface_habitable: Decimal
    periodes: tuple[PeriodePinel, ...]

    def __post_init__(self) -> None:
        if self.duree_annees not in DUREES_AUTORISEES:
            raise ValueError("La durée d'engagement Pinel doit être de 6, 9 ou 12 ans.")
        triees = sorted(self.periodes, key=lambda p: p.annee_debut)
        for p in triees:
            if p.annee_fin < p.annee_debut:
                raise ValueError(f"Période Pinel {p.annee_debut}-{p.annee_fin} invalide.")
        for avant, apres in zip(triees, triees[1:], strict=False):
            if apres.annee_debut <= avant.annee_fin:
                raise ValueError("Les périodes Pinel se chevauchent.")


def base_reduction(e: EngagementPinel) -> int:
    plafond_surface = int((PLAFOND_PAR_M2 * e.surface_habitable).to_integral_value(ROUND_HALF_UP))
    return min(e.prix_revient, PLAFOND_PRIX_REVIENT, plafond_surface)


def reduction_annee(e: EngagementPinel, annee: int) -> int:
    for p in e.periodes:
        if p.annee_debut <= annee <= p.annee_fin:
            return int((Decimal(base_reduction(e)) * p.taux_annuel / 100).quantize(Decimal(1), ROUND_DOWN))
    return 0


def reduction_cumulee(e: EngagementPinel, jusqu_a: int) -> int:
    debut = min((p.annee_debut for p in e.periodes), default=jusqu_a + 1)
    return sum(reduction_annee(e, a) for a in range(debut, jusqu_a + 1))


def reduction_totale(e: EngagementPinel) -> int:
    fin = max((p.annee_fin for p in e.periodes), default=0)
    return reduction_cumulee(e, fin)


def fin_engagement(e: EngagementPinel) -> date:
    debut = e.date_mise_en_location
    annee = debut.year + e.duree_annees
    try:
        anniversaire = debut.replace(year=annee)
    except ValueError:
        anniversaire = date(annee, 3, 1)
    return anniversaire - timedelta(days=1)


def plafond_loyer_mensuel(plafond_m2: int, surface_habitable: Decimal, surface_annexes: Decimal) -> int:
    """Plafond mensuel hors charges en centimes ; `plafond_m2` en centimes par m² (paramètre annuel de zone)."""
    surface_utile = surface_habitable + min(surface_annexes / 2, Decimal(8))
    coefficient = min(Decimal("0.7") + Decimal(19) / surface_utile, Decimal("1.2"))
    coefficient = coefficient.quantize(Decimal("0.01"), ROUND_HALF_UP)
    return int((Decimal(plafond_m2) * coefficient * surface_utile).quantize(Decimal(1), ROUND_HALF_UP))
```

Ajouter à `fiscal/__init__.py`, après les autres imports :

```python
from .pinel import (
    EngagementPinel,
    PeriodePinel,
    base_reduction,
    fin_engagement,
    plafond_loyer_mensuel,
    reduction_annee,
    reduction_cumulee,
    reduction_totale,
)
```

et compléter `__all__` avec :

```python
    "EngagementPinel", "PeriodePinel", "base_reduction", "fin_engagement", "plafond_loyer_mensuel",
    "reduction_annee", "reduction_cumulee", "reduction_totale",
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/Scripts/python.exe -m pytest tests/fiscal -q && .venv/Scripts/python.exe -m ruff check --fix .`
Expected: `42 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add fiscal/pinel.py fiscal/__init__.py tests/fiscal/test_pinel.py
git commit -m "feat(fiscal): réduction Pinel et plafond de loyer"
```
