from django import template

from commun.montants import format_euros

register = template.Library()


@register.filter
def euros(centimes):
    return "—" if centimes is None else format_euros(centimes)
