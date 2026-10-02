# Gestion de patrimoine locatif — Spécification de conception

- **Date** : 2026-10-02
- **Statut** : à relire par le propriétaire du projet
- **Approche retenue** : application Django + SQLite, conteneur Docker unique, hébergée sur Synology

## 1. Objectif

Application web personnelle permettant de :

1. saisir les loyers, frais et échéances de crédit de biens locatifs ;
2. classer chaque opération (recette imposable / non imposable, charge déductible / non déductible) ;
3. produire chaque année les montants de la déclaration **2044** (revenus fonciers, régime réel), les cases **4BA / 4BB / 4BC / 4BD** de la 2042, le suivi du **déficit foncier** et la **réduction Pinel**.

L'application est une **aide à la préparation** de la déclaration ; chaque règle cite sa source officielle (BOFiP, notice 2044) pour vérification.

### Contexte du propriétaire

- 2 appartements loués **nus**, déclarés au **régime réel (2044)**.
- Un des deux est **en fin d'engagement Pinel** (suivi complet souhaité).
- Crédit immobilier en cours, copropriété avec syndic, gestion par agence, déficit foncier antérieur à reporter.
- Un seul utilisateur. Accès **depuis Internet** via le reverse proxy DSM, sur un sous-domaine d'un nom de domaine existant.

### Critères de succès

- Pour une année donnée, l'écran « Déclaration » affiche toutes les lignes 2044 à reporter, par bien, et chaque montant est justifié par la liste des opérations et la règle appliquée.
- Les déficits sont imputés et reportés correctement (y compris la distinction intérêts / autres charges et le plafond de 10 700 €), vérifiés par des tests chiffrés.
- Les justificatifs ne sont jamais accessibles sans authentification à deux facteurs.

## 2. Périmètre

### Version 1 (ce projet)

- Biens, baux / locataires, opérations, catégories, crédit (tableau d'amortissement), copropriété, déficits, Pinel, déclaration annuelle figeable, paramètres fiscaux annuels, exports.
- Un seul calculateur fiscal : **foncier nu au régime réel**.

### Hors périmètre v1 (prévu par l'architecture)

- **Quittances de loyer** (phase 2 — le modèle Bail/Locataire les permettra).
- Autres régimes : micro-foncier, LMNP micro-BIC, LMNP réel (amortissements, 2031/2033), SCI (2072).
- Graphiques pluriannuels, import de relevés bancaires.
- Multi-utilisateur, comptabilité en partie double.

## 3. Architecture

```text
┌──────────── Synology (Container Manager) ────────────┐
│  Reverse proxy DSM  https://patrimoine.<domaine>:443 │
│            │                                         │
│            ▼  localhost:8085                         │
│  ┌─────────────── conteneur "patrimoine" ─────────┐  │
│  │ Gunicorn → Django (vues, formulaires, HTMX)    │  │
│  │              │                                 │  │
│  │              ├── app "biens", "operations", …  │  │
│  │              └── paquet "fiscal" (pur Python)  │  │
│  └───────────────┬────────────────────────────────┘  │
│   /volume1/docker/patrimoine/{data,justificatifs,backups,.env}
└──────────────────────────────────────────────────────┘
```

- **Django** (Python 3.12+), templates serveur + **HTMX** pour l'interactivité, CSS responsive (utilisable sur mobile).
- **SQLite** (un fichier dans `data/`).
- **Paquet `fiscal`** : moteur de calcul **sans dépendance à Django ni à la base**. Il reçoit des structures de données simples (dataclasses) et retourne un résultat détaillé. Testé indépendamment.
- **Calculateurs par régime** : interface commune `Calculateur.calculer(annee, biens, operations, deficits, parametres) -> ResultatFiscal`. Chaque bien porte un `regime_fiscal` ; v1 n'implémente que `FONCIER_REEL`. Les revenus fonciers et BIC restent des « paniers » séparés (pas d'imputation croisée).

## 4. Modèle de données

Toutes les opérations sont rattachées à l'année de **paiement / encaissement effectif** (comptabilité de caisse).

| Entité                              | Champs principaux                                                                                                                                                                                                                          |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Bien**                            | nom, adresse, surface habitable, surface annexes, date d'acquisition, prix de revient, `regime_fiscal` (v1 : `FONCIER_REEL`), actif                                                                                                        |
| **EngagementPinel** (0..1 par bien) | date de début, durée initiale (6/9/12), prolongations, zone, **calendrier de taux** (liste de périodes : année début, année fin, taux annuel), prix de revient retenu, surface retenue                                                     |
| **Locataire**                       | nom, coordonnées, revenu fiscal de référence à la signature, nombre de personnes du foyer                                                                                                                                                  |
| **Bail**                            | bien, locataire, date début, date fin (optionnelle), loyer hors charges, provision sur charges, dépôt de garantie                                                                                                                          |
| **Categorie**                       | code, libellé, nature (`RECETTE_IMPOSABLE`, `RECETTE_NON_IMPOSABLE`, `CHARGE_DEDUCTIBLE`, `CHARGE_NON_DEDUCTIBLE`, `INTERETS`), ligne 2044, texte d'aide, source, active. Liste préremplie, modifiable                                     |
| **Operation**                       | date de paiement, bien, catégorie, montant (centimes, positif), libellé, justificatif (fichier, optionnel), commentaire, lien optionnel vers un relevé d'agence                                                                            |
| **ReleveAgence**                    | bien, période, loyer brut, honoraires, autres retenues, net versé → génère les opérations correspondantes                                                                                                                                  |
| **Pret**                            | bien, banque, capital emprunté, date de début                                                                                                                                                                                              |
| **Echeance**                        | prêt, date, capital, intérêts, assurance emprunteur, frais (import CSV ou saisie manuelle)                                                                                                                                                 |
| **CoproprieteAnnuelle**             | bien, année, provisions versées (→ ligne 229), part non déductible issue du décompte du syndic (→ ligne 230 de l'année suivante)                                                                                                           |
| **Deficit**                         | année d'origine, nature (`REPORTABLE_FONCIER`), montant initial, montant imputé (calculé), année d'expiration (origine + 10) — saisie initiale des déficits antérieurs, puis alimentation automatique                                      |
| **ParametresAnnuels**               | année, plafond d'imputation sur revenu global (10 700 €), forfait frais de gestion par local (20 €), taux prélèvements sociaux, TMI du foyer, plafonds de loyer Pinel par zone, plafonds de ressources Pinel, cases 2042 / RICI de l'année |
| **DeclarationFigee**                | année, date, résultat complet sérialisé (JSON), empreinte des opérations prises en compte                                                                                                                                                  |

### Catégories préremplies (extrait)

| Catégorie                                                  | Nature                                      | Ligne 2044 |
| ---------------------------------------------------------- | ------------------------------------------- | ---------- |
| Loyer encaissé                                             | Recette imposable                           | 211        |
| Charges remboursées par le locataire                       | Recette non imposable                       | —          |
| Subvention ANAH / indemnité d'assurance                    | Recette imposable                           | 213 / 214  |
| Honoraires d'agence, frais de gestion, procédure           | Charge déductible                           | 221        |
| Assurance propriétaire non occupant, GLI                   | Charge déductible                           | 223        |
| Travaux de réparation, entretien, amélioration             | Charge déductible                           | 224        |
| Charges récupérables non récupérées au départ du locataire | Charge déductible                           | 225        |
| Taxe foncière (hors TEOM)                                  | Charge déductible                           | 227        |
| TEOM                                                       | Charge non déductible                       | —          |
| Provisions de copropriété                                  | Charge déductible (via CoproprieteAnnuelle) | 229        |
| Intérêts, assurance emprunteur, frais de dossier/garantie  | Intérêts                                    | 250        |
| Capital remboursé                                          | Charge non déductible                       | —          |
| Travaux de construction, reconstruction, agrandissement    | Charge non déductible                       | —          |

## 5. Moteur fiscal (`fiscal`)

### 5.1 Par bien

1. **Recettes** : somme des lignes 211–214 → ligne 215.
2. **Frais et charges** : 221 + 222 (forfait par local, ajouté automatiquement) + 223 + 224 + 225 + 226 + 227 + 229 − 230 → ligne 240.
3. **Intérêts d'emprunt** : somme des échéances de l'année (intérêts + assurance + frais) → ligne 250.
4. **Résultat du bien** = 215 − 240 − 250.

### 5.2 Global (tous les biens `FONCIER_REEL`)

Soit `R` = total recettes, `F` = total frais (240), `I` = total intérêts (250), `res = R − F − I`.

- **Si `res ≥ 0`** : `res` → **4BA** (résultat avant imputation des déficits antérieurs). Le moteur impute en parallèle les déficits antérieurs non expirés, du plus ancien au plus récent, pour tenir le stock à jour et estimer le revenu net (`revenu_net_estime`) ; l'administration fait elle-même cette imputation à partir de 4BD : ne jamais la déduire une seconde fois de 4BA.
- **Si `res < 0`** :
  - part due aux intérêts : `max(0, I − R)` → reportable sur les revenus fonciers des 10 années suivantes ;
  - part due aux autres charges : `|res| − max(0, I − R)` → imputable sur le revenu global dans la limite du plafond (10 700 €) → **4BC** ; l'excédent est reportable → ajouté au déficit reportable de l'année ;
  - déficit reportable de l'année → **4BB** ; les déficits antérieurs ne sont pas consommés.
- **4BD** : total des déficits antérieurs non expirés disponibles au début de l'année (avant imputation). À vérifier chaque année sur la notice 2044.
- **Alerte** : si un montant a été imputé sur le revenu global l'année N, le bien doit rester loué jusqu'au 31/12/N+3 ; date affichée sur le tableau de bord.
- **Estimation facultative** : impôt sur revenu foncier ≈ `revenu_net_estime` × (TMI + taux PS), et économie d'impôt ≈ 4BC × TMI.

### 5.3 Pinel

- Base = min(prix de revient, 300 000 €, 5 500 € × surface retenue).
- Réduction de l'année = base × taux de la période en cours (calendrier saisi par bien, non codé en dur).
- Affichage : réduction de l'année, cumul obtenu, restant, date de fin d'engagement, case RICI (paramètre annuel).
- Contrôle du loyer : surface utile = surface habitable + min(annexes / 2, 8 m²) ; coefficient = min(0,7 + 19 / surface utile, 1,2) ; plafond mensuel = plafond zone (€/m²) × coefficient × surface utile. Alerte si loyer HC du bail > plafond.
- Contrôle des ressources du locataire à la signature vs plafond (paramètre annuel), alerte informative.

### 5.4 Traçabilité

Chaque montant du `ResultatFiscal` porte une liste d'explications : opérations (identifiants) prises en compte et règle appliquée (texte + source). L'interface les affiche au clic.

### 5.5 Tests

- Tests unitaires `pytest` du paquet `fiscal` : exemples chiffrés de la notice 2044, et cas limites — déficit issu uniquement d'intérêts, dépassement du plafond de 10 700 €, déficit expirant, régularisation de copropriété supérieure aux provisions, année sans loyer, plusieurs biens dont un déficitaire.
- Tests Django des vues principales et de l'import CSV.

## 6. Écrans

1. **Connexion** : identifiant + mot de passe + code TOTP (obligatoire).
2. **Tableau de bord** (sélecteur d'année) : carte par bien (loyers, charges déductibles, intérêts, résultat provisoire), total, estimation d'impôt, alertes (loyer mensuel manquant, plafond Pinel, fin d'engagement Pinel, déficit expirant, obligation de location).
3. **Biens** : liste et fiche à onglets (infos, bail/locataire, crédit, Pinel, copropriété).
4. **Opérations** : liste filtrable (année, bien, catégorie), badge de nature, saisie rapide avec aide contextuelle de la catégorie, pièce jointe PDF ; saisie d'un **relevé d'agence** qui génère loyer brut (211) et honoraires (221).
5. **Crédit** : import CSV du tableau d'amortissement avec aperçu et mapping de colonnes, ou saisie manuelle ; cumul annuel intérêts / assurance / capital.
6. **Copropriété** : formulaire annuel par bien.
7. **Déficits** : tableau origine / montant / imputé / restant / expiration.
8. **Déclaration** : 2044 ligne par ligne (une colonne par bien + total), détail au clic, cases 2042, réduction Pinel, export PDF et CSV, bouton « Figer » ; alerte si une opération d'une année figée est modifiée.
9. **Paramètres** : catégories, paramètres fiscaux annuels, TMI, export complet (JSON + justificatifs en ZIP).

## 7. Déploiement et sécurité

### Conteneur

- Image unique (Python slim, Gunicorn, WhiteNoise pour les fichiers statiques), multi-architecture (amd64 / arm64), construite par **GitHub Actions** et publiée sur **ghcr.io** (dépôt privé).
- `docker-compose.yml` importé comme « Projet » dans Container Manager ; port publié uniquement sur `127.0.0.1:8085` (ou réseau interne du NAS), **non ouvert sur la box**.
- Migrations appliquées automatiquement au démarrage.
- Volumes : `/volume1/docker/patrimoine/data` (SQLite), `justificatifs/`, `backups/`, fichier `.env` (clé secrète, domaine autorisé).

### Exposition Internet

- Sous-domaine `patrimoine.<domaine existant>` → règle de **proxy inversé DSM** (443 → localhost:8085), certificat Let's Encrypt géré par DSM.
- Django : `DEBUG=False`, `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` limités au sous-domaine, `SECURE_PROXY_SSL_HEADER`, cookies `Secure`/`HttpOnly`, HSTS.
- **2FA TOTP obligatoire** (`django-otp`), verrouillage après 5 échecs (`django-axes`).
- Justificatifs servis par une vue authentifiée, jamais en statique public.
- Recommandé côté DSM : pare-feu géo-IP (France), blocage automatique d'IP. Alternative future : accès uniquement via VPN (Tailscale).

### Sauvegardes

- Sauvegarde quotidienne de la base (API `sqlite3 .backup`) dans `backups/`, rotation sur 30 jours.
- Hyper Backup du dossier `patrimoine/` vers support externe ou cloud, chiffré.
- Export JSON + ZIP des justificatifs depuis l'interface.

### Développement

- Poste Windows : environnement Python (venv) ou Docker Desktop, base de démonstration générée par une commande `seed_demo`.
- CI GitHub Actions : lint + tests à chaque push, construction de l'image sur tag.

## 8. Points à vérifier pendant l'implémentation

- Taux et cases RICI Pinel de l'année d'acquisition et des prolongations du bien concerné (saisis par le propriétaire, à partir de son avis d'imposition).
- Valeurs des paramètres annuels (plafonds Pinel, taux de prélèvements sociaux applicables aux revenus fonciers) : à saisir à partir des sources officielles de l'année, jamais codés en dur.
- Format CSV du tableau d'amortissement fourni par la banque (le mapping de colonnes est configurable à l'import).
