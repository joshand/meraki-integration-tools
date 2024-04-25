from appicm.models import *
import requests
from django.db.models import Q
from django.forms import model_to_dict
requests.packages.urllib3.disable_warnings()


module_id = "aci"


def get_tunnel_clients(args):
    outlist = []
    tclis = TunnelClient.objects.filter(Q(tenant=args[0]) | Q(tenant=get_default_tenant()))
    for tcli in tclis:
        outlist.append({"id": tcli.id, "name": tcli.description})
    return outlist


def get_token(ip, port, un, pw):
    base_path = "https://" + ip + ":" + port + "/api/aaaLogin.json"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    data = {
        "aaaUser": {
            "attributes": {
                "name": un,
                "pwd": pw
            }
        }
    }

    try:
        req = requests.request("POST", base_path, json=data, headers=headers, verify=False)
        if req.ok:
            rjson = req.json()
            token = rjson.get("imdata", [{}])[0].get("aaaLogin", {}).get("attributes", {}).get("token")
            return token
    except Exception as e:
        print(e)

    return None


def get_inventory(ip, port, api_key):
    base_path = "https://" + ip + ":" + port + "/api/node/class/fabricNode.json"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    cookies = {
        'APIC-cookie': api_key
    }

    req = requests.request("GET", base_path, headers=headers, cookies=cookies, verify=False)
    if req.ok:
        rjson = req.json()
        return rjson
    else:
        return {}


def get_system(ip, port, api_key):
    base_path = "https://" + ip + ":" + port + "/api/node/class/topSystem.json?rsp-subtree-include=health,required"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    cookies = {
        'APIC-cookie': api_key
    }

    req = requests.request("GET", base_path, headers=headers, cookies=cookies, verify=False)
    if req.ok:
        rjson = req.json()
        return rjson
    else:
        return {}


def get_apic_health(ip, port, api_key):
    base_path = "https://" + ip + ":" + port + "/api/class/infraWiNode.json"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    cookies = {
        'APIC-cookie': api_key
    }

    req = requests.request("GET", base_path, headers=headers, cookies=cookies, verify=False)
    if req.ok:
        rjson = req.json()
        return rjson
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


def parse_device_status(state_text, score_text):
    UNKNOWN = 0, 'Unknown'
    OFFLINE = 1, 'Offline'
    DORMANT = 2, 'Dormant'
    ALERTING = 3, 'Alerting'
    ONLINE = 4, 'Online'
    NOTINSTALLED = 5, 'Not Installed'

    if state_text in ["in-service", "available"]:
        if score_text in ["98", "99", "fully-fit"]:
            return ONLINE[0]
        else:
            return ALERTING[0]

    return UNKNOWN[0]


def process_inventory(tenant):
    controllers = Controller.objects.filter(tenant=tenant).filter(devicetype__name=module_id).filter(enabled=True)
    retdata = ""
    for c in controllers:
        pf_tun = c.authparm.get("api", {}).get("tunnel")
        pf_ip = c.authparm.get("api", {}).get("ip")
        pf_port = c.authparm.get("api", {}).get("port")
        pf_username = c.authparm.get("api", {}).get("username")
        pf_password = c.authparm.get("api", {}).get("password")
        plugin_id = c.devicetype.plugin_id
        my_device_type = DeviceType.objects.filter(name=module_id).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')[0]

        if not pf_ip or not pf_port or not pf_username or not pf_password or pf_ip.lower() == "none" or pf_port.lower() == "none" or pf_username.lower() == "none" or pf_password.lower() == "none":
            retdata += "- Error: Missing 'ip', 'port', 'username', or 'password' parameters.\n"
            continue
        if not pf_port or pf_port == "":
            pf_port = "443"

        token = get_token(pf_ip, pf_port, pf_username, pf_password)
        inv = get_inventory(pf_ip, pf_port, token)
        aci_systems = get_system(pf_ip, pf_port, token)
        apic_health = get_apic_health(pf_ip, pf_port, token)
        # print(json.dumps(aci_health, indent=4))

        node_dict = {}
        for aci_system in aci_systems.get("imdata", []):
            aci_attr = aci_system["topSystem"]["attributes"]
            aci_health = aci_system["topSystem"]["children"][0]["healthInst"]["attributes"]
            node_dict[aci_attr["serial"]] = {"state": aci_attr["state"], "score": aci_health["cur"]}

        for apic_system in apic_health.get("imdata", []):
            apic_attr = apic_system["infraWiNode"]["attributes"]
            node_dict[apic_attr["mbSn"]] = {"state": apic_attr["operSt"], "score": apic_attr["health"]}

        for dev_verbose in inv.get("imdata", []):
            device = dev_verbose["fabricNode"]["attributes"]
            mdl, err = lookup_device_model(plugin_id, device["model"])
            if err:
                retdata += err
            if mdl is not None:
                retdata += "* ACI: " + str(device["serial"])
                node_status = parse_device_status(node_dict[device["serial"]]["state"], node_dict[device["serial"]]["score"])
                res, created = Device.objects.update_or_create(tenant=tenant, serial_number=device["serial"],
                                                               defaults={"basemac": None, "orphaned": False,
                                                                         "name": device["model"],
                                                                         "rawconfig": device,
                                                                         "devicetype": my_device_type,
                                                                         "controller": c,
                                                                         "devicemodeltype": mdl,
                                                                         "current_version": device["version"],
                                                                         "status": node_status})
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
        ret = process_inventory(tenant)
        if ret:
            TaskResult.objects.create(tenant=tenant, taskname="sync_" + module_id, result=ret)


def run():
    do_sync()
