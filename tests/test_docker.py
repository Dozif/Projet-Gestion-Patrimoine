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
