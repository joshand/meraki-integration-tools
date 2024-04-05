from appicm.models import *
from django.forms import model_to_dict
from django.db.models import Q


def get_script(pm):
    uz = Upload.objects.filter(tenant_id=pm.tenant.id).filter(plugin_id=pm.plugin_id).filter(description=pm.name + ".py")
    if len(uz) == 0:
        uz = Upload.objects.filter(tenant_id=get_default_tenant()).filter(plugin_id=pm.plugin_id).filter(description=pm.name + ".py")
    if len(uz) > 0:
        pmn = "scripts." + str(uz[0].filename()).replace(".py", "")
        return pmn

    return None


def get_template(pm):
    uz = Upload.objects.filter(Q(tenant_id=pm.tenant.id) | Q(tenant_id=get_default_tenant())).filter(uploadzip__description=pm.name)

    for upl in uz:
        if ".html" in upl.file.name:
            pmn = "custom/" + str(upl.filename())
            return pmn

    return None


def get_menu(pm, item_type):
    if item_type == "plugin":
        uz = CustomMenu.objects.filter(customtemplate__pluginmodule__id=pm.id)
    elif item_type == "integration":
        uz = CustomMenu.objects.filter(customtemplate__integrationmodule__id=pm.id)
    else:
        return None

    if len(uz) == 1:
        return uz[0].name
    # else:
    #     print(pm.id, uz)

    return None
