import json
from django import template
import pytz
from appicm.models import *


register = template.Library()


@register.filter
def pretty_json(value):
    try:
        j = json.dumps(json.loads(value), indent=4)
    except Exception:
        j = value
    return j


@register.filter
def apikey(value):
    if value:
        showpart = value[-4:]
        outkey = ("*" * (len(value) - 4)) + showpart
        return outkey

    return value


@register.filter
def password(value):
    if value:
        outkey = "*" * (len(value))
        return outkey

    return value


@register.filter
def batch(iterable, n=1):
    if iterable:
        l = len(iterable)
        for ndx in range(0, l, n):
            yield iterable[ndx:min(ndx + n, l)]

    return []


@register.filter
def localtime(value, user):
    au = AppUser.objects.filter(user=user)
    if len(au) == 1:
        cst = pytz.timezone(au[0].localtz)
        return value.astimezone(cst).replace(tzinfo=None)
    else:
        return value


@register.filter
def lookup(dictlookup, key):
    try:
        return dictlookup.get("api", {}).get(key, None)
    except Exception:
        return dictlookup


@register.filter
def dump(jsonval):
    return json.dumps(jsonval)


@register.filter
def makestring(value):
    print(value)
    return str(value)


@register.filter
def display(value, filt):
    if value:
        filt_list = filt.split("|")
        if filt_list[0] == "slice":
            sl1 = filt_list[1]
            sl2 = filt_list[2]
            if sl1 == "":
                sl1 = 0
            else:
                sl1 = int(sl1)
            if sl2 == "":
                sl2 = len(value)
            else:
                sl2 = int(sl2)
            return "<span title='" + value + "'>..." + value[sl1:sl2] + "</span>"

    return value
