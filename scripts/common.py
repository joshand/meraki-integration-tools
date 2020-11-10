from appicm.models import *


def get_script(pm):
    uz = Upload.objects.filter(tenant_id=pm.tenant.id).filter(description=pm.py_mod_name + ".py")
    if len(uz) == 0:
        uz = Upload.objects.filter(tenant_id=get_default_tenant()).filter(description=pm.py_mod_name + ".py")
    if len(uz) > 0:
        pmn = "scripts." + str(uz[0].filename()).replace(".py", "")
        return pmn

    return None


def get_template(pm):
    uz = Upload.objects.filter(tenant_id=pm.tenant.id).filter(description=pm.py_mod_name + ".html")
    if len(uz) == 0:
        uz = Upload.objects.filter(tenant_id=get_default_tenant()).filter(description=pm.py_mod_name + ".html")
    if len(uz) > 0:
        pmn = "custom/" + str(uz[0].filename())
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

    return None
