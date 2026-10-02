# Gestion de patrimoine locatif

Application personnelle de suivi des locations vides (régime réel, déclaration 2044), installée sur un Synology.

## Lancer l'application sur le PC (développement)

Depuis Git Bash, à la racine du projet :

    py -3.14 -m venv .venv
    .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
    export DJANGO_DEBUG=1
    .venv/Scripts/python.exe manage.py migrate
    .venv/Scripts/python.exe manage.py createsuperuser
    .venv/Scripts/python.exe manage.py seed_demo      # facultatif : données fictives 2025
    .venv/Scripts/python.exe manage.py runserver

Ouvrir http://127.0.0.1:8000/, se connecter, puis scanner le QR code avec une application
d'authentification (double authentification obligatoire).

La base SQLite et les justificatifs sont dans `var/` (ignoré par git).

## Tests

    .venv/Scripts/python.exe -m pytest -q
    .venv/Scripts/python.exe -m ruff check .

## Avertissement

L'application aide à préparer la déclaration ; vérifiez chaque année les montants avec la notice 2044
et les paramètres fiscaux (Paramètres → Paramètres annuels).

## Installer sur le Synology

Suivre [docs/INSTALLATION-SYNOLOGY.md](docs/INSTALLATION-SYNOLOGY.md). Archive à copier sur le NAS :
`bash scripts/creer_archive.sh` (dans `dist/`).
