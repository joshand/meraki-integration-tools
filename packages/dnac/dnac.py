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


def get_dnac_auth(ip, port, un, pw):
    url = "https://" + ip + ":" + port + "/dna/system/api/v1/auth/token"
    r = requests.post(url, auth=(un, pw), verify=False)
    if "error" in r.json():
        return None

    return json.loads(r.text)["Token"]


def get_dnac_inventory(ip, port, authtoken):
    url = "https://" + ip + ":" + port + "/dna/intent/api/v1/network-device"
    headers = {
        "X-Auth-Token": authtoken,
        "Content-Type": "application/json"
    }
    # print(headers)
    r = requests.get(url, headers=headers, verify=False)
    if r.text.find("An invalid response was received from the upstream server") >= 0:
        return "An error occurred: " + r.text
    else:
        u_json = json.loads(r.text)

    return u_json["response"]


def get_dnac_cluster(ip, port, authtoken):
    url = "https://" + ip + ":" + port + "/dna/intent/api/v1/nodes-config"
    headers = {
        "X-Auth-Token": authtoken,
        "Content-Type": "application/json"
    }
    # print(headers)
    r = requests.get(url, headers=headers, verify=False)
    if r.text.find("An invalid response was received from the upstream server") >= 0:
        return "An error occurred: " + r.text
    else:
        u_json = json.loads(r.text)

    return u_json["response"]


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


def process_dnac_inventory(tenant):
    controllers = Controller.objects.filter(tenant=tenant).filter(devicetype__name="dnac").filter(enabled=True)
    retdata = ""
    for c in controllers:
        pf_tun = c.authparm.get("api", {}).get("tunnel")
        pf_ip = c.authparm.get("api", {}).get("ip")
        pf_port = c.authparm.get("api", {}).get("port")
        pf_username = c.authparm.get("api", {}).get("username")
        pf_password = c.authparm.get("api", {}).get("password")
        plugin_id = c.devicetype.plugin_id
        my_device_type = DeviceType.objects.filter(name="dnac").exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')[0]

        if not pf_ip or not pf_username or not pf_password or pf_ip.lower() == "none" or pf_username.lower() == "none" or pf_password.lower() == "none":
            retdata += "- Error: Missing 'ip', 'port', 'username' or 'password' parameters.\n"
            continue
        if not pf_port or pf_port == "":
            pf_port = "443"

        token = get_dnac_auth(pf_ip, pf_port, pf_username, pf_password)
        if token is None:
            retdata += "- Error: Error with Authentication.\n"
            continue

        cluster = get_dnac_cluster(pf_ip, pf_port, token)
        for node in cluster.get("nodes", []):
            model = node.get("platform", {}).get("product", None)
            mdl, err = lookup_device_model(plugin_id, model)
            if err:
                retdata += err
            if mdl is not None:
                sn = node.get("platform", {}).get("serial", "")
                retdata += "* Controller: " + str(sn)
                res, created = Device.objects.update_or_create(tenant=tenant, serial_number=sn,
                                                               defaults={"basemac": None, "orphaned": False,
                                                                         "name": model,
                                                                         "rawconfig": node,
                                                                         "devicetype": my_device_type,
                                                                         "controller": c,
                                                                         "devicemodeltype": mdl})
                if created:
                    retdata += " (Added)\n"
                else:
                    retdata += " (Updated)\n"

        devices = get_dnac_inventory(pf_ip, pf_port, token)
        for device in devices:
            model = device.get("platformId", None)
            mdl, err = lookup_device_model(plugin_id, model)
            if err:
                retdata += err
            if mdl is not None:
                sn = device.get("serialNumber", "")
                mac = device.get("macAddress", "")
                name = device.get("name", mac)
                retdata += "* Device: " + str(sn)
                res, created = Device.objects.update_or_create(tenant=tenant, serial_number=sn,
                                                               defaults={"basemac": mac, "orphaned": False,
                                                                         "name": name,
                                                                         "rawconfig": device,
                                                                         "devicetype": my_device_type,
                                                                         "controller": c,
                                                                         "devicemodeltype": mdl})
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
        ret = process_dnac_inventory(tenant)
        if ret:
            TaskResult.objects.create(tenant=tenant, taskname="sync_dnac", result=ret)


def run():
    do_sync()
