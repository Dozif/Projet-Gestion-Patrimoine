import os
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_DEBUG", "1")

from .settings import *  # noqa: E402, F403

AXES_ENABLED = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="patrimoine-tests-"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PATRIMOINE_INSCRIPTION_LIBRE = True
PATRIMOINE_CODE_INSTALLATION = ""
STATIC_ROOT = Path(tempfile.mkdtemp(prefix="patrimoine-static-"))
