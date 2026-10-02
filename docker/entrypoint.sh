#!/bin/sh
# Prépare le dossier de données, applique les migrations, crée le compte si besoin,
# puis lance Gunicorn sous l'utilisateur non privilégié « patrimoine ».
set -e
mkdir -p /data/justificatifs /data/sauvegardes
chown -R patrimoine:patrimoine /data
lancer() { setpriv --reuid=patrimoine --regid=patrimoine --init-groups "$@"; }
lancer python manage.py migrate --noinput
lancer python manage.py initialiser_compte
exec setpriv --reuid=patrimoine --regid=patrimoine --init-groups \
    gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile -
