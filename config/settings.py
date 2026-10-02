"""Réglages de l'application. Les valeurs sensibles viennent des variables d'environnement."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être défini en production.")
    SECRET_KEY = "dev-uniquement-ne-pas-utiliser-en-production"
if not DEBUG and (SECRET_KEY == "a-remplacer" or len(SECRET_KEY) < 50):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY doit être une clé aléatoire d'au moins 50 caractères (voir le guide)."
    )

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

DATA_DIR = Path(os.environ.get("PATRIMOINE_DATA_DIR", BASE_DIR / "var"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "axes",
    "commun",
    "comptes",
    "biens",
    "operations",
    "credit",
    "fiscalite",
    "declaration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "comptes.middleware.DoubleAuthentificationObligatoire",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "commun.context_processors.navigation",
            ],
        },
    },
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "patrimoine.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("PATRIMOINE_STATIC_ROOT", BASE_DIR / "staticfiles"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
SAUVEGARDES_DIR = DATA_DIR / "sauvegardes"
# Pas de MEDIA_URL : les justificatifs ne sont servis que par une vue authentifiée.
MEDIA_ROOT = Path(os.environ.get("PATRIMOINE_MEDIA_DIR", DATA_DIR / "justificatifs"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "comptes:connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "comptes:connexion"
SESSION_COOKIE_AGE = 8 * 60 * 60

OTP_TOTP_ISSUER = "Patrimoine"

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # heure
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["username"]
# Un seul compte, derrière le reverse proxy de DSM : le blocage par identifiant protège le mot de passe
# quelle que soit l'adresse IP de l'attaquant (l'IP vue par Django est celle du proxy).
SILENCED_SYSTEM_CHECKS = ["axes.W006"]

# Enrôlement de la double authentification : en production, le QR code n'est montré qu'après saisie
# du code d'installation défini dans .env (un mot de passe volé ne suffit pas à enrôler un téléphone).
PATRIMOINE_CODE_INSTALLATION = os.environ.get("PATRIMOINE_CODE_INSTALLATION", "")
PATRIMOINE_INSCRIPTION_LIBRE = DEBUG

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # La redirection HTTPS est faite par le reverse proxy de DSM ; le conteneur n'écoute qu'en local (127.0.0.1).
    # Le préchargement HSTS engagerait tout le domaine du propriétaire : volontairement non activé.
    SILENCED_SYSTEM_CHECKS += ["security.W008", "security.W021"]
