from appicm.models import *
import requests
from django.db.models import Q
from django.forms import model_to_dict
requests.packages.urllib3.disable_warnings()


def get_tunnel_clients(args):
    outlist = []
    tclis = TunnelClient.objects.filter(Q(tenant=args[0]) | Q(tenant=get_default_tenant()))
    for tcli in tclis:
        outlist.append({"id": tcli.id, "name": tcli.description})
    return outlist


def get_freenas_inventory(ip, port, api_key):
    url = "https://" + ip + ":" + port + "/api/v2.0/system/info"
    headers = {
        "Accept": "*/*",
        "Authorization": "Bearer " + api_key
    }

    r = requests.get(url, headers=headers, verify=False)
    if r.ok:
        return r.json()
    else:
        return {}


def get_freenas_health(ip, port, api_key):
    url = "https://" + ip + ":" + port + "/api/v2.0/alert/list"
    headers = {
        "Accept": "*/*",
        "Authorization": "Bearer " + api_key
    }

    r = requests.get(url, headers=headers, verify=False)
    if r.ok:
        return r.json()
    else:
        return {}


def lookup_device_model(plugin_id, model_string):
    if model_string is None:
        return None, None

    # my_device_model = DeviceModelType.objects.filter(plugin_id=plugin_id).filter(name=model_string)
    my_device_model = DeviceModelType.objects.filter(name=model_string)
    if len(my_device_model) <= 0:
        return None, "(Error: Unable to find model '" + str(model_string) + "' in database.)\n"
    else:
        if len(my_device_model) == 1:
            return my_device_model[0], None
        else:
            return None, None


def parse_device_logs(log_list):
    found_error = False
    for h in log_list:
        if h["level"] not in ["INFO"]:
            found_error = True

    UNKNOWN = 0, 'Unknown'
    OFFLINE = 1, 'Offline'
    DORMANT = 2, 'Dormant'
    ALERTING = 3, 'Alerting'
    ONLINE = 4, 'Online'
    NOTINSTALLED = 5, 'Not Installed'

    if found_error:
        return ALERTING[0]
    else:
        return ONLINE[0]

    return UNKNOWN[0]


def process_freenas_inventory(tenant):
    controllers = Controller.objects.filter(tenant=tenant).filter(devicetype__name="freenas").filter(enabled=True)
    retdata = ""
    for c in controllers:
        pf_tun = c.authparm.get("api", {}).get("tunnel")
        pf_ip = c.authparm.get("api", {}).get("ip")
        pf_port = c.authparm.get("api", {}).get("port")
        pf_apikey = c.authparm.get("api", {}).get("apikey")
        plugin_id = c.devicetype.plugin_id
        my_device_type = DeviceType.objects.filter(name="freenas").exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')[0]

        if not pf_ip or not pf_apikey or pf_ip.lower() == "none" or pf_apikey.lower() == "none":
            retdata += "- Error: Missing 'ip', 'port' or 'pf_apikey' parameters.\n"
            continue
        if not pf_port or pf_port == "":
            pf_port = "443"

        node = get_freenas_inventory(pf_ip, pf_port, pf_apikey)
        health = get_freenas_health(pf_ip, pf_port, pf_apikey)
        status = parse_device_logs(health)
        ver = node.get("version")
        model = node.get("system_product")
        sn = node.get("system_serial")

        mdl, err = lookup_device_model(plugin_id, model)
        if err:
            retdata += err
        if mdl is not None:
            retdata += "* NAS: " + str(sn)
            res, created = Device.objects.update_or_create(tenant=tenant, serial_number=sn,
                                                           defaults={"basemac": None, "orphaned": False,
                                                                     "name": model,
                                                                     "rawconfig": node,
                                                                     "devicetype": my_device_type,
                                                                     "controller": c,
                                                                     "devicemodeltype": mdl,
                                                                     "current_version": ver,
                                                                     "status": status})
            if created:
                retdata += " (Added)\n"
            else:
                retdata += " (Updated)\n"

    return retdata


def do_sync(tenant_list=None):
    if not tenant_list:
        tenants = Tenant.objects.exclude(name="Default")
    else:
        tenants = Tenant.objects.filter(id__in=tenant_list)

    for tenant in tenants:
        ret = process_freenas_inventory(tenant)
        if ret:
            TaskResult.objects.create(tenant=tenant, taskname="sync_freenas", result=ret)


def run():
    do_sync()
