import pytest


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user("proprietaire", password="mot-de-passe-solide-123")
