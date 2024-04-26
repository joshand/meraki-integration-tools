import meraki
import meraki.exceptions
from appicm.models import *


# def_icon = "https://meraki.cisco.com/wp-content/uploads/2020/07/icon-solutions-digital-workplace-hover.svg"


def get_home_link(ctl):
    base_url = ctl.authparm.get("api", {}).get("baseurl", None)
    api_key = ctl.authparm.get("api", {}).get("key", None)
    org_id = ctl.authparm.get("api", {}).get("orgid", None)
    if not base_url or not api_key or not org_id:
        return ctl.mgmtaddress
    dashboard = meraki.DashboardAPI(base_url=base_url, api_key=api_key, suppress_logging=True,
                                    print_console=False, output_log=False, caller=settings.CUSTOM_UA)

    org = dashboard.organizations.getOrganization(org_id)
    return org["url"]


def getorgs(args):
    if len(args) < 2:
        return None
    dashboard = meraki.DashboardAPI(base_url=args[0], api_key=args[1], suppress_logging=True,
                                    print_console=False, output_log=False, caller=settings.CUSTOM_UA)
    orgs = dashboard.organizations.getOrganizations()
    for org in orgs:
        org["name"] = org["name"].replace("'", "`").replace('"', "`")
    return orgs


# def config_connection(request, tenant_id):
#     if request.method == 'POST':
#         mer_id = request.POST.get("merId")
#         mer_desc = request.POST.get("merDesc")
#         mer_key = request.POST.get("merKey")
#         mer_org = request.POST.get("merOrg")
#         if mer_id is None or mer_id == "":
#             mer = DeviceType.objects.filter(name="Meraki")
#             authdata = {"api": {"orgid": mer_org, "key": mer_key, "baseurl": "https://api.meraki.com/api/v1"}}
#             cont = Controller.objects.create(name=mer_desc, devicetype=mer[0], authparm=authdata, tenant_id=tenant_id)
#             orgurl = get_basic_data(cont, "orgurl", default="https://dashboard.meraki.com")
#             HomeLink.objects.create(name=mer_desc, url=orgurl, controller=cont, icon_url=def_icon)
#         else:
#             controllers = Controller.objects.filter(id=mer_id)
#             if len(controllers) == 1:
#                 cont = controllers[0]
#                 cont.name = mer_desc
#                 cont.authparm["api"]["orgid"] = mer_org
#                 if mer_key.find("*") < 0:
#                     cont.authparm["api"]["key"] = mer_key
#                 cont.save()
#                 orgurl = get_basic_data(cont, "orgurl", default="https://dashboard.meraki.com")
#                 HomeLink.objects.update_or_create(controller=cont, tenant_id=tenant_id,
#                                                   defaults={"name": mer_desc, "url": orgurl, "icon_url": def_icon})
# 
#     if request.GET.get("action") == "delorg":
#         mer_id = request.GET.get("id")
#         Controller.objects.filter(id=mer_id).delete()
# 
#     dashboards = Controller.objects.filter(tenant=tenant_id).filter(devicetype__name="Meraki")
# 
#     return {"template": "home/config_dashboard.html", "desc": "Meraki Dashboard", "data": dashboards}


def parse_device_status(status_text):
    UNKNOWN = 0, 'Unknown'
    OFFLINE = 1, 'Offline'
    DORMANT = 2, 'Dormant'
    ALERTING = 3, 'Alerting'
    ONLINE = 4, 'Online'
    NOTINSTALLED = 5, 'Not Installed'

    if status_text == "alerting":
        return ALERTING[0]
    if status_text == "dormant":
        return DORMANT[0]
    if status_text == "offline":
        return OFFLINE[0]
    if status_text == "online":
        return ONLINE[0]

    return UNKNOWN[0]


def process_meraki_inventory(tenant):
    retdata = "--This is the Meraki Dashboard Discovery module--\n"
    controllers = Controller.objects.filter(tenant=tenant).filter(devicetype__name="Meraki").filter(enabled=True)
    if len(controllers) == 0:
        return None

    my_device_type = DeviceType.objects.filter(name="Meraki").exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')[0]
    lst_port_type = L1InterfaceType.objects.filter(name="802.3ab").first()
    lst_vlan_type = L2InterfaceType.objects.filter(name="VLAN").first()
    lst_trunk = L2DomainType.objects.filter(name="Trunk").first()
    lst_access = L2DomainType.objects.filter(name="Access").first()
    if lst_port_type and lst_vlan_type and lst_trunk and lst_access:
        process_interfaces = True
        my_port_type = lst_port_type
        my_vlan_type = lst_vlan_type
        my_trunk = lst_trunk
        my_access = lst_access
    else:
        process_interfaces = False
    for c in controllers:
        retdata += "Controller: " + str(c.name) + "\n"
        plugin_id = c.devicetype.plugin_id
        base_url = c.authparm.get("api", {}).get("baseurl")
        api_key = c.authparm.get("api", {}).get("key")
        org_id = c.authparm.get("api", {}).get("orgid")
        if not base_url or not api_key or not org_id:
            retdata += "- Error: Missing 'baseurl', 'key', or 'orgid' parameter.\n"
            continue

        dashboard = meraki.DashboardAPI(base_url=base_url, api_key=api_key, suppress_logging=True,
                                        print_console=False, output_log=False, caller=settings.CUSTOM_UA)
        inv = dashboard.organizations.getOrganizationInventoryDevices(org_id)
        inv2 = dashboard.organizations.getOrganizationDevices(org_id)
        inv3 = dashboard.organizations.getOrganizationDevicesStatuses(org_id)

        device_json = {}
        dev_l3 = {}
        for i in inv2:
            device_json[i["serial"]] = {"version": i["firmware"]}
            if i["productType"] == "switch":
                try:
                    inv4 = dashboard.switch.getDeviceSwitchRoutingInterfaces(i["serial"])
                    if len(inv4) > 0:
                        dev_l3[i["serial"]] = {"data": inv4, "type": "switch", "stack": None}
                    stacks = dashboard.switch.getNetworkSwitchStacks(i["networkId"])
                    for stack in stacks:
                        inv5 = dashboard.switch.getNetworkSwitchStackRoutingInterfaces(i["networkId"], stack["id"])
                        if len(inv5) > 0:
                            dev_l3[stack["id"]] = {"data": inv5, "type": "stack", "stack": stack}
                except:
                    pass
            elif i["productType"] == "appliance":
                try:
                    inv4 = dashboard.appliance.getNetworkApplianceVlans(i["networkId"])
                    if len(inv4) > 0:
                        dev_l3[i["serial"]] = {"data": inv4, "type": "appliance", "stack": None}
                    inv5 = dashboard.appliance.getNetworkApplianceSingleLan(i["networkId"])
                    if inv5:
                        dev_l3[i["serial"]] = {"data": [inv5], "type": "appliance_single", "stack": None}
                except:
                    pass

        for device_or_stack in dev_l3:
            elem_type = dev_l3[device_or_stack]["type"]
            elem_stack = dev_l3[device_or_stack]["stack"]
            for l3interface in dev_l3[device_or_stack]["data"]:
                if elem_type in ["switch", "stack"]:
                    int_name = l3interface["name"]
                    int_subnet = l3interface["subnet"]
                    int_ip = l3interface["interfaceIp"]
                    int_vlan = l3interface["vlanId"]
                elif elem_type in ["appliance"]:
                    int_name = l3interface["name"]
                    int_subnet = l3interface["subnet"]
                    int_ip = l3interface["applianceIp"]
                    int_vlan = l3interface["id"]
                elif elem_type in ["appliance_single"]:
                    int_name = device_or_stack
                    int_subnet = l3interface["subnet"]
                    int_ip = l3interface["applianceIp"]
                    int_vlan = 1
                else:
                    continue

                vlan_obj, _ = VLAN.objects.update_or_create(tenant=tenant, number=int_vlan, defaults={"name": int_name})
                if elem_type == "stack":
                    for sw_sn in elem_stack["serials"]:
                        # print(sw_sn, elem_stack, Device.objects.filter(serial_number=sw_sn))
                        dev = Device.objects.filter(serial_number=sw_sn).first()
                        subnet_obj, created = Subnet.objects.update_or_create(tenant=tenant, subnet=int_subnet,
                                                                              defaults={"name": int_name,
                                                                                        "vlan": vlan_obj})
                        subnet_obj.device.add(dev)
                        subnet_obj.save()
                        if created:
                            subnet_obj.autoscan = False
                            subnet_obj.save()

                        address_obj, created = Address.objects.update_or_create(tenant=tenant, subnet=subnet_obj,
                                                                                address=int_ip,
                                                                                defaults={"description": int_name + " (DG)",
                                                                                          "status": 2})
                        address_obj.device.add(dev)
                        address_obj.save()
                else:
                    dev = Device.objects.filter(serial_number=device_or_stack).first()
                    subnet_obj, created = Subnet.objects.update_or_create(tenant=tenant, subnet=int_subnet,
                                                                          defaults={"name": int_name,
                                                                                    "vlan": vlan_obj})
                    subnet_obj.device.add(dev)
                    subnet_obj.save()
                    if created:
                        subnet_obj.autoscan = False
                        subnet_obj.save()

                    address_obj, created = Address.objects.update_or_create(tenant=tenant, subnet=subnet_obj,
                                                                            address=int_ip,
                                                                            defaults={"description": int_name + " (DG)",
                                                                                      "status": 2})
                    address_obj.device.add(dev)
                    address_obj.save()
                # print(subnet_obj, address_obj)

        for i in inv3:
            device_json[i["serial"]]["status"] = parse_device_status(i["status"])

        # print(device_json)
        devlist = []
        devices = Device.objects.filter(tenant=tenant).filter(controller=c)
        for device in devices:
            devlist.append(str(device.serial_number))

        for device in inv:
            sn = device["serial"]
            retdata += "* Device: " + str(sn)
            if sn in devlist:
                devlist.remove(sn)

#             my_device_model = DeviceModelType.objects.filter(name=device["model"]).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
#             my_device_model = DeviceModelType.objects.filter(plugin_id=plugin_id).filter(name=device["model"])
            my_device_model = DeviceModelType.objects.filter(name=device["model"])
            if len(my_device_model) <= 0:
                retdata += "(Error: Unable to find model '" + str(device["model"]) + "' in database.)\n"
                continue

            if sn not in device_json:
                dev_ver = "N/A: Device parked in inventory"
                dev_status = 5                  # Not Installed
            else:
                dev_ver = device_json.get(sn, {}).get("version")
                dev_status = device_json.get(sn, {}).get("status")

            if dev_ver in ["Not running configured version", "Firmware locked. Please contact support."]:
                dev_ver = "N/A: " + dev_ver

            # print(dev_ver, sn, device_json.get(sn))
            res, created = Device.objects.update_or_create(tenant=tenant, serial_number=sn,
                                                           defaults={"basemac": device["mac"], "orphaned": False,
                                                                     "name": device["name"] if device["name"] else device["mac"],
                                                                     "rawconfig": device,
                                                                     "devicetype": my_device_type,
                                                                     "controller": c,
                                                                     "devicemodeltype": my_device_model[0],
                                                                     "current_version": dev_ver,
                                                                     "status": dev_status})
            if created:
                retdata += "(Added)\n"
            else:
                retdata += "(Updated)\n"

            devtype = res.devicemodeltype.device_type
            if process_interfaces:
                if devtype == "security_appliance" and device["networkId"]:
                    mxvlans = dashboard.appliance.getNetworkApplianceVlansSettings(device["networkId"]).get("vlansEnabled")
                else:
                    mxvlans = False

                if (devtype == "switch" or (devtype == "security_appliance" and mxvlans)) and device["networkId"]:
                    if devtype == "switch":
                        ports = dashboard.switch.getDeviceSwitchPorts(sn)
                    else:
                        ports = dashboard.appliance.getNetworkAppliancePorts(device["networkId"])
                    retdata += "** Ports: " + str(len(ports)) + "\n"
                    for port in ports:
                        if devtype == "switch":
                            portnum = port["portId"]
                        else:
                            portnum = str(port["number"])

                        l1i, created = L1Interface.objects.update_or_create(tenant=tenant, device=res, name=portnum,
                                                                            l1interfacetype=my_port_type,
                                                                            defaults={"description": port.get("name"),
                                                                                      "rawdata": port})
                        # print(l1i.rawdata, port)
                        # l1iu = L1Interface.objects.filter(id=str(l1i.id))[0]
                        # l1iu.rawdata = port
                        # l1iu.save()

                        retdata += "*** " + str(l1i) + " -- " + str(created) + "\n"
                        if port.get("vlan"):
                            vlanid, created = L2Interface.objects.update_or_create(tenant=tenant,
                                                                                   l2interfacetype=my_vlan_type,
                                                                                   number=str(port["vlan"]),
                                                                                   defaults={
                                                                                      "name": "VLAN " + str(port["vlan"])})
                        else:
                            vlanid, created = L2Interface.objects.get_or_create(tenant=tenant, l2interfacetype=my_vlan_type,
                                                                                number="1")

                        if port["type"] == "trunk":
                            L2Domain.objects.update_or_create(tenant=tenant, l1interface=l1i,
                                                              defaults={"l2domaintype": my_trunk,
                                                                        "l2interface": vlanid,
                                                                        "allowedrange": "1-4094" if port.get("allowedVlans") == "all" else
                                                                        port.get("allowedVlans")})
                        else:
                            L2Domain.objects.update_or_create(tenant=tenant, l1interface=l1i,
                                                              defaults={"l2domaintype": my_access,
                                                                        "l2interface": vlanid,
                                                                        "allowedrange": "1-4094" if port.get("allowedVlans") == "all" else
                                                                        port.get("allowedVlans", str(vlanid.number))})
                else:
                    pcount = res.devicemodeltype.portcount
                    pstr = res.devicemodeltype.portlist
                    if pcount and int(pcount) > 0:
                        plist = pstr.replace("\r\n", ",").split(",")
                        for pid in plist:
                            L1Interface.objects.update_or_create(tenant=tenant, device=res, name=str(pid), l1interfacetype=my_port_type)

        for device in devlist:
            retdata += "= Device Orphaned: " + device + "\n"
            Device.objects.filter(tenant=tenant).filter(serial_number=device).update(orphaned=True)

        # save new networks
        existing_network_ids = []
        nets = dashboard.organizations.getOrganizationNetworks(org_id)
        for net in nets:
            existing_network_ids.append(str(net["id"]))
            Construct.objects.update_or_create(tenant=tenant, constructId=net["id"],
                                               defaults={"name": net["name"], "type": "network", "rawdata": net,
                                                         "controller": c})

        # clean up non-existant networks
        dbnets = Construct.objects.filter(tenant=tenant).filter(controller=c)
        for dbnet in dbnets:
            # print(dbtun.tunnelId, existing_tunnel_ids)
            if str(dbnet.constructId) not in existing_network_ids:
                retdata += "removed superfluous network '" + dbnet.name + "'\n"
                dbnet.delete()

        # save new tunnels
        existing_tunnel_ids = []
        tuns = dashboard.appliance.getOrganizationApplianceVpnThirdPartyVPNPeers(org_id)
        for tun in tuns["peers"]:
            existing_tunnel_ids.append(str(tun["publicIp"]))
            t, cr = Tunnel.objects.update_or_create(tenant=tenant, tunnelId=tun["publicIp"],
                                                    defaults={"name": tun["name"], "rawdata": tun, "controller": c})
            if not cr:
                t.rawdata = tun
                t.save()

        # clean up non-existant tunnels
        dbtuns = Tunnel.objects.filter(tenant=tenant).filter(controller=c)
        for dbtun in dbtuns:
            # print(dbtun.tunnelId, existing_tunnel_ids)
            if str(dbtun.tunnelId) not in existing_tunnel_ids:
                retdata += "removed superfluous tunnel '" + dbtun.name + "'\n"
                dbtun.delete()


    return retdata

    # if orgid == 0:
    #     orglist = meraki.myorgaccess(apitoken, suppressprint=True)
    #     orgprint = []
    #     orgheader = ["Org. ID", "Name"]
    #     for o in orglist:
    #         orgprint.append([o["id"], o["name"]])
    #
    #     # print(tabulate(orgprint, headers=orgheader))
    #     return {"debug": "do_meraki_inventory. No Organization specified; unable to continue.\n", "data": {}}
    # else:
    #     # print(orgid)
    #     devlist = meraki.getorginventory(apitoken, orgid, suppressprint=True)
    #     return {"debug": "do_meraki_inventory.\n", "data": devlist}


# def meraki_get_base_info(ip, apitoken, orgid):
#     debugout = "- Getting Meraki Inventory...\n"
#     ret = do_meraki_inventory(ip, apitoken, orgid)
#     debugout += ret["debug"]
#     udata = ret["data"]
#
#     # discoverytag = "dashboard.meraki_discovery"
#     # orgid = 0
#     # for o in range(0, len(sys.argv[1:])):
#     #     if sys.argv[1:][o] == "--orgid":
#     #         orgid = sys.argv[1:][o+1]
#
#     # discover.doprint("- Adding Device Info to NetBox...")
#     # mfgid = discover.create_mfg("Cisco Systems Inc")
#     # dtid = discover.create_dev_type("Meraki Dashboard", 1, mfgid)
#     # drid = discover.create_dev_role("Dashboard", "009900")
#     # siteid = discover.create_site("Home")
#     # devid = discover.create_device("Meraki Dashboard (" + str(orgid) + ")", "dashboard.meraki.com-" + str(orgid), siteid, mfgid, dtid, drid, status=1, discovery=discoverytag)
#     # # intid = discover.create_interface("Dashboard", "", devid, "", discovery=discoverytag)
#     # # ipid = discover.create_ipaddress(ip, "/24", intid)
#     # # discover.update_device(devid, ipid)
#     # srid = discover.create_secret_role("Meraki Dashboard")
#     # seskey = discover.get_secret_session_key()
#     # secid = discover.create_secret("apikey", apitoken, devid, srid, seskey)
#
#     # for dev in udata:
#     #     mfgid = discover.create_mfg("Cisco Systems Inc")
#     #     dtid = discover.create_dev_type(dev["model"], 1, mfgid)
#     #     drid = discover.create_dev_role(get_family(dev["model"]), "009900")
#     #     siteid = discover.create_site("Home")
#     #     if dev["name"] is None or dev["name"] == "":
#     #         devname = dev["mac"]
#     #     else:
#     #         devname = dev["name"]
#     #     devid = discover.create_device(devname, dev["serial"], siteid, mfgid, dtid, drid, status=5, discovery=discoverytag)
#     #     # intid = discover.create_interface("Public IP", "", devid, "")
#     #     # ipid = discover.create_ipaddress(dev["publicIp"], "/24", intid)
#     #     # discover.update_device(devid, ipid)
#     return {"debug": debugout, "data": udata}


# def controller_discovery(authparm, devip="dashboard.meraki.com"):
#     jauth = json.loads(authparm)
#
#     debugout = "--This is the Meraki Dashboard Discovery module--\n"
#     mout = meraki_get_base_info(devip, jauth["api"]["X-Cisco-Meraki-API-Key"], jauth["api"]["orgid"])
#
#     return {"debug": debugout + mout["debug"], "data": mout["data"]}


def do_sync(tenant_list=None):
    if not tenant_list:
        tenants = Tenant.objects.exclude(name="Default")
    else:
        tenants = Tenant.objects.filter(id__in=tenant_list)

    for tenant in tenants:
        ret = process_meraki_inventory(tenant)
        if ret:
            TaskResult.objects.create(tenant=tenant, taskname="sync_dashboard", result=ret)


def run():
    do_sync()
