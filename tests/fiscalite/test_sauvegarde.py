import sqlite3

import pytest
from django.core.management import call_command

from tests.aides import creer_bien

pytestmark = pytest.mark.django_db(transaction=True)


def test_sauvegarde_lisible(settings, tmp_path):
    settings.SAUVEGARDES_DIR = tmp_path
    creer_bien()
    call_command("sauvegarder")
    fichiers = list(tmp_path.glob("patrimoine-*.sqlite3"))
    assert len(fichiers) == 1
    with sqlite3.connect(fichiers[0]) as copie:
        assert copie.execute("select count(*) from biens_bien").fetchone()[0] == 1


def test_rotation_des_sauvegardes(settings, tmp_path):
    settings.SAUVEGARDES_DIR = tmp_path
    for i in range(32):
        (tmp_path / f"patrimoine-20200101-0000{i:02d}-000000.sqlite3").write_bytes(b"ancien")
    call_command("sauvegarder", garder=30)
    call_command("sauvegarder", garder=30)
    restants = sorted(p.name for p in tmp_path.glob("patrimoine-*.sqlite3"))
    assert len(restants) == 30
    assert sum(1 for nom in restants if not nom.startswith("patrimoine-2020")) == 2
