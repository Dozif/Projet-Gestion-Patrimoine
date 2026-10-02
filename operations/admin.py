from django.contrib import admin

from .models import Categorie


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ["libelle", "nature", "ligne_2044", "active", "ordre"]
    list_filter = ["nature", "active"]
