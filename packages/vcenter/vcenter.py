from appicm.models import *
import requests
from django.db.models import Q
from django.forms import model_to_dict
requests.packages.urllib3.disable_warnings()
from pyVmomi import vim
from pyVim import connect
import ssl


module_id = "vcenter"


def get_tunnel_clients(args):
    outlist = []
    tclis = TunnelClient.objects.filter(Q(tenant=args[0]) | Q(tenant=get_default_tenant()))
    for tcli in tclis:
        outlist.append({"id": tcli.id, "name": tcli.description})
    return outlist


def get_hw_details(ip, port, un, pw):
    host_map = {}
    # https://stackoverflow.com/questions/34307713/hosthardwaresummary-in-pyvomi
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.verify_mode = ssl.CERT_NONE
    service_instance = connect.SmartConnect(host=ip, port=port, user=un, pwd=pw, sslContext=context)
    search_index = service_instance.content.searchIndex
    root_folder = service_instance.content.rootFolder
    view_ref = service_instance.content.viewManager.CreateContainerView(container=root_folder, type=[vim.HostSystem],
                                                                        recursive=True)
    for host in view_ref.view:
        # print(host.hardware.systemInfo)
        host_serial = None
        for sii in host.hardware.systemInfo.otherIdentifyingInfo:
            # print(sii.identifierType.key, sii.identifierValue)
            if sii.identifierType.key == 'ServiceTag':
                host_serial = sii.identifierValue

        # print(host.hardware.systemInfo)
        h = str(host).replace("'", "").split(":")
        host_map[h[1]] = {"model": host.summary.hardware.model, "version": host.summary.config.product.fullName, "serial": host_serial, "overall_status": host.summary.overallStatus}
        # print(host.hardware.systemInfo.serialNumber)
        # print(host)
        # print(host.summary.hardware.uuid)
        # print(host.summary.hardware.model)
    view_ref.Destroy

    token = get_token(ip, port, un, pw)
    inv = get_inventory(ip, port, token)
    for host in inv:
        if host["host"] not in host_map:
            host_map[host["host"]] = {"model": "Unknown", "version": "Unknown"}
        host_map[host["host"]]["hostname"] = host["name"]
        host_map[host["host"]]["state"] = host["connection_state"]
        host_map[host["host"]]["power"] = host["power_state"]

    return host_map


def get_token(ip, port, un, pw):
    url = "https://" + ip + ":" + port + "/api/session"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        req = requests.request("POST", url, headers=headers, auth=(un, pw), verify=False)
        if req.ok:
            token = req.json()
            if token:
                return token
    except:
        print("Exception")

    return None


def get_inventory(ip, port, api_key):
    url = "https://" + ip + ":" + port + "/api/vcenter/host"
    headers = {
        "Accept": "application/json",
        "vmware-api-session-id": api_key
    }

    req = requests.request("GET", url, headers=headers, verify=False)
    if req.ok:
        return req.json()
    else:
        return {}


def get_inventory_vm(ip, port, api_key):
    url = "https://" + ip + ":" + port + "/api/vcenter/vm"
    headers = {
        "Accept": "application/json",
        "vmware-api-session-id": api_key
    }

    req = requests.request("GET", url, headers=headers, verify=False)
    if req.ok:
        return req.json()
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


def parse_device_status(state_text, status_text):
    UNKNOWN = 0, 'Unknown'
    OFFLINE = 1, 'Offline'
    DORMANT = 2, 'Dormant'
    ALERTING = 3, 'Alerting'
    ONLINE = 4, 'Online'
    NOTINSTALLED = 5, 'Not Installed'

    if state_text == "vm":
        if status_text == "POWERED_ON":
            return ONLINE[0]
        elif status_text == "POWERED_OFF":
            return OFFLINE[0]
        else:
            return UNKNOWN[0]

    if state_text == "CONNECTED":
        if status_text == "green":
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

        if not pf_ip or not pf_username or not pf_password or pf_ip.lower() == "none" or pf_username.lower() == "none" or pf_password.lower() == "none":
            retdata += "- Error: Missing 'ip', 'port', 'username', or 'password' parameters.\n"
            continue
        if not pf_port or pf_port == "":
            pf_port = "443"

        host_map = get_hw_details(pf_ip, pf_port, pf_username, pf_password)
        for host_name in host_map:
            host = host_map[host_name]
            # print(host)
            mdl, err = lookup_device_model(plugin_id, host["model"])
            if err:
                retdata += err
            if mdl is not None:
                if host["serial"] is None:
                    retdata += "* Error: ESXi server has missing serial number\n"
                else:
                    retdata += "* ESXi: " + str(host["serial"])
                    host_status = parse_device_status(host["state"], host["overall_status"])
                    res, created = Device.objects.update_or_create(tenant=tenant, serial_number=host["serial"],
                                                                   defaults={"basemac": None, "orphaned": False,
                                                                             "name": host["model"],
                                                                             "rawconfig": host,
                                                                             "devicetype": my_device_type,
                                                                             "controller": c,
                                                                             "devicemodeltype": mdl,
                                                                             "current_version": host["version"],
                                                                             "status": host_status})
                    if created:
                        retdata += " (Added)\n"
                    else:
                        retdata += " (Updated)\n"

        token = get_token(pf_ip, pf_port, pf_username, pf_password)
        vms = get_inventory_vm(pf_ip, pf_port, token)
        for vm in vms:
            mdl, err = lookup_device_model(plugin_id, "Virtual Machine")
            retdata += "* VM: " + str(vm["vm"])
            vm_status = parse_device_status("vm", vm["power_state"])
            res, created = Device.objects.update_or_create(tenant=tenant, serial_number=vm["vm"],
                                                           defaults={"basemac": None, "orphaned": False,
                                                                     "name": vm["name"],
                                                                     "rawconfig": vm,
                                                                     "devicetype": my_device_type,
                                                                     "controller": c,
                                                                     "devicemodeltype": mdl,
                                                                     "current_version": "N/A",
                                                                     "status": vm_status})
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
