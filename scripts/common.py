from appicm.models import *


def get_default_tenant():
    deften = Tenant.objects.filter(name="Default")
    if len(deften) == 1:
        return deften[0].id
    else:
        deften = Tenant.objects.create(name="Default")
        return deften


def get_script(pm):
    uz = Upload.objects.filter(tenant=pm.tenant).filter(description=pm.py_mod_name + ".py")
    if len(uz) > 0:
        pmn = "scripts." + str(uz[0].filename()).replace(".py", "")
        return pmn

    return None
