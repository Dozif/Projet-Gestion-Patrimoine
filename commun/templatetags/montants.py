from django import template

from commun.montants import format_euros
from fiscal import en_euros

register = template.Library()


@register.filter
def euros(centimes):
    return "—" if centimes is None else format_euros(centimes)


@register.filter
def euros_entiers(centimes):
    return "—" if centimes is None else format_euros(en_euros(centimes) * 100)
