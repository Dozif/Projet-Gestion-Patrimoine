import os
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def test_reglages_de_production_sans_avertissement():
    donnees = tempfile.mkdtemp(prefix="patrimoine-prod-")
    env = {
        **os.environ,
        "DJANGO_DEBUG": "0",
        "DJANGO_SECRET_KEY": "une-cle-de-test-tres-longue-et-aleatoire-0123456789-abcdefghijklmnop",
        "DJANGO_ALLOWED_HOSTS": "patrimoine.exemple.fr",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://patrimoine.exemple.fr",
        "PATRIMOINE_DATA_DIR": donnees,
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    r = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=RACINE, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-c", "from django.conf import settings; import django; django.setup(); "
         "print('whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE)"],
        cwd=RACINE, env=env, capture_output=True, text=True,
    )
    assert r.stdout.strip() == "True", r.stderr
