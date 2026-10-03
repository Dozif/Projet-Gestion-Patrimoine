from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def lire(nom):
    return (RACINE / nom).read_text(encoding="utf-8")


def test_le_port_n_ecoute_qu_en_local_et_les_donnees_sont_persistantes():
    compose = lire("docker-compose.yml")
    assert '"127.0.0.1:8085:8000"' in compose
    assert "./data:/data" in compose
    assert "env_file: .env" in compose


def test_l_image_n_embarque_aucun_secret_ni_donnee():
    ignores = lire(".dockerignore").split()
    for motif in (".env", "data", "var", ".venv", ".git"):
        assert motif in ignores


def test_le_point_d_entree_migre_puis_lance_gunicorn_sans_root():
    entree = lire("docker/entrypoint.sh")
    assert entree.index("migrate") < entree.index("initialiser_compte") < entree.index("gunicorn")
    assert "setpriv --reuid=patrimoine" in entree
    assert "PATRIMOINE_CODE_INSTALLATION" in lire(".env.example")


def test_fins_de_ligne_linux_pour_les_fichiers_du_conteneur():
    attributs = lire(".gitattributes")
    for motif in ("*.sh", "Dockerfile", "*.yml"):
        assert f"{motif} text eol=lf" in attributs


def test_image_robuste():
    dockerfile = lire("Dockerfile")
    assert "command -v setpriv" in dockerfile
    assert 'ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint.sh"]' in dockerfile
    assert "tzdata" in lire("requirements.txt")
    assert "choisir" in lire(".env.example")


def test_dockerfile_sans_sequence_d_echappement_litterale():
    assert chr(92) + "n" not in lire("Dockerfile")


def test_conteneur_sans_nouveaux_privileges_et_tmp_borne():
    compose = lire("docker-compose.yml")
    assert "no-new-privileges:true" in compose
    assert "/tmp:size=" in compose


def test_options_gunicorn_explicites():
    entree = lire("docker/entrypoint.sh")
    for option in ("--timeout 30", "--limit-request-line 4094", "--limit-request-fields 100"):
        assert option in entree


def test_le_guide_ne_fait_jamais_ouvrir_les_donnees_a_tout_le_monde():
    guide = lire("docs/INSTALLATION-SYNOLOGY.md")
    assert "Everyone" not in guide
    assert "chown -R 1000:1000" in guide


def test_le_guide_documente_le_secours_et_le_changement_de_telephone():
    guide = lire("docs/INSTALLATION-SYNOLOGY.md")
    assert "## Secours" in guide
    assert "changepassword" in guide
    assert "debloquer_2fa" in guide
    assert "Supprimer" in guide and "TOTP" in guide
    assert "client_max_body_size" in guide
