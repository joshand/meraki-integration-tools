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


def get_platform_details(args):
    pf_tun = args[0]
    pf_ip = args[1]
    pf_port = args[2]
    pf_username = args[3]
    pf_password = args[4]
    if not pf_ip or not pf_username or not pf_password:
        return {"status": "error", "data": "Please input all parameters"}
    if not pf_port or pf_port == "":
        pf_port = "443"

    url = 'https://'+pf_ip+':'+pf_port+'/restconf/data/Cisco-IOS-XE-device-hardware-oper:device-hardware-data'

    headers = {
        'Content-type': 'application/yang-data+json',
        'Accept': 'application/yang-data+json'
    }

    platform = requests.get(url, verify=False, auth=(pf_username, pf_password), headers=headers, timeout=20)
    if platform.status_code != 200:
        return {"status": "error", "data": platform.json()}
    return {"status": "ok", "data": platform.json()}


def process_platform_inventory(tenant):
    controllers = Controller.objects.filter(tenant=tenant).filter(devicetype__name="iosxe16")
    out_cont = []
    for c in controllers:
        pf_tun = c.authparm.get("api", {}).get("tunnel")
        pf_ip = c.authparm.get("api", {}).get("ip")
        pf_port = c.authparm.get("api", {}).get("port")
        pf_username = c.authparm.get("api", {}).get("username")
        pf_password = c.authparm.get("api", {}).get("password")

        if not pf_ip or not pf_username or not pf_password or pf_ip.lower() == "none" or pf_username.lower() == "none" or pf_password.lower() == "none":
            out_cont.append({str(c.id): {"status": "error", "data": "Please input all parameters"}})
            continue
        if not pf_port or pf_port == "":
            pf_port = "443"

        # print(c.authparm, pf_ip, pf_port, pf_username, pf_password)
        url = 'https://'+pf_ip+':'+pf_port+'/restconf/data/Cisco-IOS-XE-device-hardware-oper:device-hardware-data'

        headers = {
            'Content-type': 'application/yang-data+json',
            'Accept': 'application/yang-data+json'
        }

        platform = requests.get(url, verify=False, auth=(pf_username, pf_password), headers=headers, timeout=20)
        if platform.ok:
            out_cont.append({str(c.id): {"status": "ok", "data": platform.json()}})
        else:
            out_cont.append({str(c.id): {"status": "error", "code": platform.status_code, "data": platform.content.decode("utf-8")}})
    return out_cont


def do_sync(tenant_list=None):
    if not tenant_list:
        tenants = Tenant.objects.exclude(name="Default")
    else:
        tenants = Tenant.objects.filter(id__in=tenant_list)

    for tenant in tenants:
        ret = process_platform_inventory(tenant)
        if ret:
            TaskResult.objects.create(tenant=tenant, taskname="sync_iosxe", result=ret)


def run():
    do_sync()
