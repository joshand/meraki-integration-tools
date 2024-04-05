import json
from django import template
import pytz
from appicm.models import *
import base64
from django.apps import apps


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
    # print(dictlookup.get(key, None), dictlookup, key)
    try:
        if "api" in dictlookup:
            return dictlookup.get("api", {}).get(key, None)
        else:
            return dictlookup.get(key, "")
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
            lpad = ""
            rpad = ""
            if sl1 == "" or sl1 == "0":
                sl1 = 0
                lpad = ""
            else:
                sl1 = int(sl1)
                lpad = "..."
            if sl2 == "":
                sl2 = len(value)
                rpad = ""
            else:
                sl2 = int(sl2)
                rpad = "..."
            newval = value[sl1:sl2]
            if newval == value:
                return "<span title='" + value + "'>" + newval + "</span>"
            else:
                return "<span title='" + value + "'>" + lpad + newval + rpad + "</span>"
        elif filt_list[0] == "lookup":
            if value == "-1":
                return "<span title='" + value + "'>N/A</span>"
            else:
                sl1 = filt_list[1]
                sl2 = filt_list[2]
                mdl = apps.get_model('appicm', sl1)
                q = mdl.objects.filter(id__iexact=value)
                if len(q) != 1:
                    return "<span title='" + value + "'>Unknown</span>"
                else:
                    return "<span title='" + value + "'>" + getattr(q.first(), sl2) + "</span>"
                # print(sl1, sl2, mdl, value, q.objects.all())

    return value


@register.filter
def get_distances(value):
    if value:
        thesite = Site.objects.filter(id=value)
        return thesite.calculate_distances()

    return []


@register.filter
def get_children(value):
    children = LocationHierarchy.objects.filter(parent_id=value)
    return children


@register.filter
def remove_dash(value):
    if str(value)[-1:] == "-":
        return str(value)[:-1]

    return str(value)


@register.filter
def get_action_icons(value):
    html = ""
    if value.locationtype.tier == 0:
        return "&nbsp;"
    else:
        if value.locationtype.haslocation:
            html += """
                <a title="Edit """ + str(value.locationtype.description) + """" onclick="loadModalNew('Edit """ + str(value.locationtype.description) + """', '""" + str(value.id) + """', '""" + str(value.description) + """', '""" + str(value.address) + """', '')"><span class="icon icon-edit_24"></span></a>
            """
        else:
            if value.locationtype.other_fields:
                of = value.locationtype.other_fields
                of_val = value.custom_data.get(of, None)
                html += """
                    <a title="Edit """ + str(value.locationtype.description) + """" onclick="loadSimpleModal('Edit """ + str(value.locationtype.description) + """', '', '""" + str(value.id) + """', '""" + str(value.description) + """', '""" + str(value.description) + """', '""" + str(of) + """', '""" + str(of_val) + """')"><span class="icon icon-edit_24"></span></a>
                """
            else:
                html += """
                    <a title="Edit """ + str(value.locationtype.description) + """" onclick="loadSimpleModal('Edit """ + str(value.locationtype.description) + """', '', '""" + str(value.id) + """', '""" + str(value.description) + """', '""" + str(value.description) + """', '', '')"><span class="icon icon-edit_24"></span></a>
                """

        html += """
            <a title="Delete """ + str(value.locationtype.description) + """" href="/home/settings-sites/""" + str(value.locationtype.description) + """?id=""" + str(value.id) + """&action=del""" + str(value.locationtype.description) + """"><span class="icon icon-delete_24"></span></a>
        """

    if value.locationtype.haslocation:
        dist = base64.b64encode(json.dumps(value.calculate_distances(max_entries=10)).encode('ascii')).decode('ascii')
        html += """
            <a title="Select Location Code" onclick="loadCLLIModal('""" + str(value.id) + """', '""" + dist + """');"><span class="icon icon-view-list_24"></span></a>
        """

    if value.locationtype.description in ["Rack", "rack"]:
        html += """
            <a title="Rack Layout" href="/home/settings-layout?rack=""" + str(value.id) + """"><span class="icon icon-annotation-legacy_16" style="font-size: 1.6em;"></span></a>
        """

    html += """
        <a title="Add """ + str(value.locationtype.description) + """" onclick="loadSimpleModal('Add """ + str(value.locationtype.description) + """', '""" + str(value.id) + """', '', '""" + str(value.locationtype.description) + """', '', '', '');"><span class="icon icon-add_24"></span></a>
    """

    return html
