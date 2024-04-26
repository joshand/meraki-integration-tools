import base64
import csv

from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import views as auth_views
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import redirect, reverse, render
from django.http import HttpResponse, JsonResponse
from django.views.generic import TemplateView
from appicm.serializers import *
from appicm.models import *
from appicm.forms import *
from django.db.models import F, Q
import scripts
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.utils import timezone
from .forms import UploadForm
from scripts.common import get_script, get_template, get_menu
from rest_framework import status
import logging
from django.forms import model_to_dict
from django.shortcuts import get_object_or_404
import requests
import googlemaps
from rest_framework.permissions import IsAuthenticated
import ipaddress
from .serializers import DeviceSerializer


@xframe_options_exempt
def status_task_result(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    taskid = request.META['PATH_INFO'].split("/")[-1:][0]
    if request.user.is_superuser:
        trs = TaskResult.objects.filter(Q(tenant=tenant) | Q(tenant=get_default_tenant(obj=True))).filter(id=taskid)
    else:
        trs = TaskResult.objects.filter(tenant=tenant).filter(id=taskid)
    if len(trs) == 1:
        return JsonResponse({"data": trs[0].result.replace("\n", "<br>")})
    else:
        return JsonResponse({"data": "Error loading results."})


def make_tunnel_request(inportnum, body, headers, method):
    try:
        url = "http://127.0.0.1:" + str(inportnum)
        r = requests.request(method, url, json=body, headers=headers, timeout=30)
        return True, r
    except Exception as e:
        print("exception", e)
        return False, e


def tenant(request):
    if not request.user.is_authenticated:
        return redirect('/')

    tenants = request.user.appuser.tenant.all()
    return render(request, 'general/tenant.html',
                  {"tenants": tenants, "baseurl": "http://" + request.get_host() + "/home"})


# def check_tenant_old(request):
#     if not request.user.is_authenticated:
#         return None, None, None
#
#     tenant_id = None
#
#     tenant_get = request.GET.get('tenant', None)
#     if tenant_get:
#         tenant_id = tenant_get
#     else:
#         value = request.COOKIES.get('tenant_id')
#         if value is not None:
#             tenant_id = value
#
#     if not tenant_id:
#         return None, None, None
#
#     tenants = Tenant.objects.filter(id=tenant_id)
#     if len(tenants) != 1:
#         return None, None, None
#     else:
#         tenant = tenants[0]
#
#     tdesc = tenant.name[:13] + "..." if len(tenant.name) > 13 else tenant.name
#     tenants = request.user.appuser.tenant.all()
#
#     return tenant_id, tenants, tdesc


def get_tenant(request):
    if not request.user.is_authenticated:
        return None

    tenant_id = None

    tenant_get = request.GET.get('tenant', None)
    if tenant_get:
        tenant_id = tenant_get
    else:
        value = request.COOKIES.get('tenant_id')
        if value is not None:
            tenant_id = value

    if not tenant_id:
        return None

    tenants = Tenant.objects.filter(id=tenant_id)
    if len(tenants) != 1:
        return None
    else:
        return tenants[0]


def get_globals(request, tenant):
    g = {"tenants": request.user.appuser.tenant.all(), "connections": get_connections(tenant),
         "menus": get_menus(tenant)}
    return g


def get_menus(tenant):
    cm = CustomMenu.objects.filter(Q(tenant=tenant) | Q(tenant=get_default_tenant()))
    return cm


def home(request):
    # tenant_id, tenants, tdesc = check_tenant(request)
    # if not tenant_id:
    #     return redirect('/tenant')
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    homelinks = HomeLink.objects.filter(tenant=tenant)
    sites = Site.objects.filter(tenant=tenant)
    site_list = []
    for site in sites:
        site_list.append({"lat": site.geolocation.lat, "lng": site.geolocation.lon})

    crumbs = '<li class="breadcrumb-item active">Home</li>'
    response = render(request, 'home/home.html', {"baseurl": "http://" + request.get_host() + "/home", "crumbs": crumbs,
                                                  "tenant": tenant, "global": get_globals(request, tenant),
                                                  "homelinks": homelinks, "sites": site_list,
                                                  "google_api_key": settings.GOOGLE_MAPS_API_KEY,
                                                  "menuopen": "home",
                                                  })

    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def show_config(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    get_act = request.GET.get("action")

    if get_act == "delete":
        obj_id = request.GET.get("id")
        lo = LocationObject.objects.filter(tenant=tenant, id=obj_id).first()
        lh = LocationHierarchy.objects.filter(tenant=tenant, object=lo).first()
        child = LocationHierarchy.objects.filter(tenant=tenant, parent=lo).first()
        child.parent = lh.parent
        child.save()
        lh.delete()
        lo.delete()
        # print(lo, lh, child)

    if request.method == 'POST':
        print(request.POST)
        act = request.POST.get("action")
        if act == "addChild":
            description = request.POST.get("description")
            parent_id = request.POST.get("parent_id")
            location_type = request.POST.get("location_type")

            lo = LocationObject.objects.create(tenant=tenant, description=description, locationtype_id=location_type)
            lh = LocationHierarchy.objects.create(tenant=tenant, object=lo, parent_id=parent_id)
        elif act == "moveLocation":
            move_object_id = request.POST.get("move_object_id")
            move_new_location = request.POST.get("move_new_location")
            lo = LocationObject.objects.filter(id=move_object_id).first()
            ln = LocationObject.objects.filter(id=move_new_location).first()
            lh = LocationHierarchy.objects.filter(object=lo).first()
            lh.parent = ln
            lh.save()
            # print(lo, ln, lh)
        elif act == "editLocation":
            edit_object_id = request.POST.get("edit_object_id")
            location_description = request.POST.get("location_description")
            location_address = request.POST.get("location_address")
            update_geolocation_p = request.POST.get("update_geolocation")
            location_code_addon = request.POST.get("location_code_addon")
            if update_geolocation_p == "on":
                update_geolocation = True
            else:
                update_geolocation = False

            if update_geolocation and location_address not in ["", None]:
                gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
                geocode_result = gmaps.geocode(location_address)
                if len(geocode_result) > 0:
                    loc_raw = geocode_result[0].get("geometry", {}).get("location", None)
                    loc = str(loc_raw.get("lat")) + "," + str(loc_raw.get("lng"))
                else:
                    loc = ""
            else:
                loc = ""

            LocationObject.objects.filter(id=edit_object_id).update(description=location_description, address=location_address, geolocation=loc, clli_addon=location_code_addon)
        elif act == "setCLLI":
            clli_object_id = request.POST.get("clli_object_id")
            clli = request.POST.get("clli")
            custom_location_code = request.POST.get("custom_location_code")

            print(clli_object_id, clli, custom_location_code)

            if clli == "custom":
                c = CustomCLLI.objects.create(clli=custom_location_code)
                LocationObject.objects.filter(id=clli_object_id).update(clli_id=None, custom_clli=c)
            else:
                LocationObject.objects.filter(id=clli_object_id).update(clli_id=clli, custom_clli=None)

        else:
            objType = request.POST.get("objType")
            if objType == "site":
                siteid = request.POST.get("siteId")
                sitedesc = request.POST.get("siteDesc")
                siteaddr = request.POST.get("siteAddr")
                gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
                geocode_result = gmaps.geocode(siteaddr)
                if len(geocode_result) > 0:
                    loc_raw = geocode_result[0].get("geometry", {}).get("location", None)
                    # loc = "lat=" + str(loc_raw.get("lat")) + ",long=" + str(loc_raw.get("lng"))
                    loc = str(loc_raw.get("lat")) + "," + str(loc_raw.get("lng"))
                else:
                    loc = None

                if siteid == "":
                    Site.objects.create(tenant=tenant, name=sitedesc, address=siteaddr, geolocation=loc)
                else:
                    Site.objects.filter(id=siteid).update(name=sitedesc, address=siteaddr, geolocation=loc)
            elif objType == "floor":
                parentid = request.POST.get("parentId")
                objId = request.POST.get("objId")
                objName = request.POST.get("objDesc")

                if objId == "":
                    Floor.objects.create(tenant=tenant, site_id=parentid, name=objName)
                else:
                    Floor.objects.filter(id=objId).update(name=objName)
            elif objType == "room":
                parentid = request.POST.get("parentId")
                objId = request.POST.get("objId")
                objName = request.POST.get("objDesc")

                if objId == "":
                    Room.objects.create(tenant=tenant, floor_id=parentid, name=objName)
                else:
                    Room.objects.filter(id=objId).update(name=objName)
            elif objType == "row":
                parentid = request.POST.get("parentId")
                objId = request.POST.get("objId")
                objName = request.POST.get("objDesc")

                if objId == "":
                    Row.objects.create(tenant=tenant, room_id=parentid, name=objName)
                else:
                    Row.objects.filter(id=objId).update(name=objName)
            elif objType == "rack":
                parentid = request.POST.get("parentId")
                objId = request.POST.get("objId")
                objName = request.POST.get("objDesc")
                objRU = request.POST.get("s_objFld1")

                if objId == "":
                    Rack.objects.create(tenant=tenant, row_id=parentid, name=objName, height=objRU)
                else:
                    Rack.objects.filter(id=objId).update(name=objName, height=objRU)
            elif objType == "clli":
                cityid = request.POST.get("cityId")
                selected_clli = request.POST.get("selectedclli")

                if cityid == "":
                    pass
                else:
                    CityState.objects.filter(id=cityid).update(clli_id=selected_clli)

    # intopts = IntegrationModule.objects.filter(Q(tenant__name="Default") | Q(tenant_id=tenant_id))
    # intconfigs = IntegrationConfiguration.objects.filter(tenant_id=tenant_id)
    # avail_opts = []
    # unavail_opts = []
    # for intopt in intopts:
    #     pm1_dts = intopt.pm1.devicetype.all()
    #     pm2_dts = intopt.pm2.devicetype.all()
    #     pm1_cont = Controller.objects.filter(devicetype__in=pm1_dts)
    #     pm2_cont = Controller.objects.filter(devicetype__in=pm2_dts)
    #     if len(pm1_cont) > 0 and len(pm2_cont) > 0:
    #         avail_opts.append(intopt)
    #     else:
    #         unavail_opts.append(intopt)
    # sites = Site.objects.filter(tenant=tenant)
    # cities = CityState.objects.filter(tenant=tenant)
    hierarchy_locations = LocationHierarchy.objects.filter(tenant=tenant).filter(parent__locationtype__tier=0)

    crumbs = '<li class="breadcrumb-item active">Settings</li>'
    return render(request, "home/tenant_settings.html", {"crumbs": crumbs, "tenant": tenant,
                                                         "global": get_globals(request, tenant),
                                                         "data": hierarchy_locations,
                                                         "menuopen": "settings-sites", "ddopen": "settings"})


def show_layout(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    rackid = request.GET.get("rack")

    if request.method == 'POST':
        # print(request.POST)
        chg = base64.b64decode(request.POST.get("changes", "").encode("ascii")).decode("ascii")

        # rackid = request.POST.get("rack")
        lo = LocationObject.objects.filter(id=rackid)
        ed = lo.first().custom_data
        ed["data"] = json.loads(chg)
        lo.update(custom_data=ed)

    thislo = LocationObject.objects.filter(id=rackid).first()
    if thislo:
        size_ru = thislo.custom_data.get("RU", 42)
        data = thislo.custom_data.get("data", [])
    else:
        size_ru = 42
        data = []

    enc_data = base64.b64encode(json.dumps(data).encode("ascii")).decode("ascii")

    crumbs = '<li class="breadcrumb-item">Settings</li><li class="breadcrumb-item active">Sites</li>'
    return render(request, "home/rack_layout.html", {"crumbs": crumbs, "tenant": tenant,
                                                     "global": get_globals(request, tenant),
                                                     "rack": rackid, "data": enc_data, "size": size_ru})


def api_get_devices(request):
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse([], safe=False)

    devices = {"data": []}
    devs = Device.objects.filter(tenant=tenant)
    for dev in devs:
        dev_icon = """
            <div id='""" + str(dev.id) + """' class="text-center text-white grid-stack-item newWidget ui-draggable" gs-x="0" gs-y="2" gs-w="11" gs-h="1" gs-id='""" + str(dev.id) + """'>
                <div class="grid-stack-item-content">
                    <div style="padding-top:7px">
                        <span class="icon icon-generic-device_24"></span>
                    </div>
                </div>
            </div>
        """
        plugin_id = dev.devicetype.plugin_id
        module_name = PluginModule.objects.filter(plugin_id=plugin_id).first()
        if module_name:
            show_name = module_name.description
        else:
            show_name = dev.devicetype.name

        devices["data"].append({"id": str(dev.id),
                                "visible": True,
                                "name": str(dev.name),
                                "version": str(dev.current_version),
                                "status": str(dev.get_status()),
                                "basemac": str(dev.basemac),
                                "devicetype": str(show_name),
                                "serial_number": str(dev.serial_number),
                                "devicemodeltype": str(dev.devicemodeltype.name),
                                "icon": dev_icon,
                                "DT_RowId": "row_" + str(dev.id)
                                })

    return JsonResponse(devices, safe=False)


def api_get_subnets(request):
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse([], safe=False)

    subnets = {"data": []}
    sns = Subnet.objects.filter(tenant=tenant)
    for sn in sns:
        dev_text = "<br>".join([str(obj) for obj in sn.device.all()])
        subnets["data"].append({"id": str(sn.id),
                                "visible": True,
                                "name": "<a href='/home/ipam-address?subnet=" + str(sn.id) + "'>" + str(sn.name) + "</a>",
                                "subnet": str(sn.subnet),
                                "vlan": str(sn.vlan.number),
                                "device": dev_text,
                                "usage": str(sn.get_usage()),
                                "autoscan": str(sn.autoscan),
                                "actions": "<a href='#' onclick='loadModal(\"" + str(sn.id) + "\", \"" + str(sn.name) + "\", \"" + str(sn.subnet) + "\", \"" + str(sn.autoscan) + "\")'><i class='ph ph-pencil' style='font-size: 20px'></i></a>",
                                "DT_RowId": "row_" + str(sn.id)
                                })

    return JsonResponse(subnets, safe=False)


def api_get_addresses(request):
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse([], safe=False)

    subnets = {"data": []}
    subnet_id = request.GET.get("subnet")
    addrs = Address.objects.filter(tenant=tenant, subnet_id=subnet_id)
    ip_list = []
    for addr in addrs:
        ip_list.append(str(addr.address))
        dev_text = "<br>".join([str(obj) for obj in addr.device.all()])
        subnets["data"].append({"id": str(addr.id),
                                "visible": True,
                                "ip": str(addr.address),
                                "description": addr.description,
                                "device": dev_text,
                                "status": addr.get_status(),
                                "actions": "",
                                "DT_RowId": "row_" + str(addr.id)
                                })

    ips = ipaddress.IPv4Network(addrs.first().subnet.subnet).hosts()
    for ip in ips:
        if str(ip) not in ip_list:
            subnets["data"].append({"id": None,
                                    "visible": True,
                                    "ip": str(ip),
                                    "description": "",
                                    "device": "",
                                    "status": "Unused",
                                    "actions": "",
                                    "DT_RowId": "row_" + str(ip)
                                    })

    return JsonResponse(subnets, safe=False)


def get_parents(location_obj):
    ptypes = get_parent_types(location_obj.locationtype)
    parents = LocationObject.objects.filter(locationtype_id__in=ptypes)

    plist = []
    for p in parents:
        plist.append({"id": str(p.id), "description": p.description, "type": p.locationtype.description})
    return plist


def get_parent_types(location_obj):
    parent_obj = location_obj.parent.first()
    if parent_obj:
        return [parent_obj.id] + get_parent_types(parent_obj)

    return []


def get_children(location_obj):
    if location_obj.child:
        return [{"id": str(location_obj.child.id), "description": location_obj.child.description}] + get_children(location_obj.child)

    return []


def get_locations(locations_query, counter, level, root_node=False):
    if len(locations_query) == 0:
        return [], counter

    # print(locations_query, counter, level)
    ll = []
    for hl in locations_query:
        counter += 1
        if root_node:
            obj = hl.parent
        else:
            obj = hl.object
        ll_id = str(obj.id)
        ll_icon = obj.locationtype.iconname
        if root_node:
            ll_desc = obj.description
        else:
            ll_desc = obj.locationtype.description + ": " + obj.description
        ll_addr = str(obj.address) if obj.address else ""
        ll_code = str(obj.get_clli()) if obj.get_clli() else ""
        ll_act_edit = "<a href='#' title='Edit " + obj.locationtype.description + "' onclick='loadEditModal(\"" + obj.locationtype.description + "\", \"" + str(obj.id) + "\", \"" + str(obj.description) + "\", \"" + str(obj.address) + "\", \"" + str(obj.locationtype.hasclli_addon) + "\", \"" + str(obj.clli_addon) + "\")'><i class='ph ph-pencil' style='font-size: 20px'></i></a>"
        ll_act_del = "<a title='Delete " + obj.locationtype.description + "' href='/home/settings-sites" + "?id=" + str(obj.id) + "&action=delete" + "'><i class='ph ph-trash' style='font-size: 20px'></i></a>"

        parents = get_parents(obj)
        parents_b64 = base64.b64encode(json.dumps(parents).encode('ascii')).decode('ascii')
        ll_act_move = "<a href='#' title='Move " + obj.locationtype.description + "' onclick='loadMoveModal(\"" + obj.locationtype.description + "\", \"" + str(obj.id) + "\", \"" + str(obj.description) + "\", \"" + parents_b64 + "\")'><i class='ph ph-arrow-u-up-right' style='font-size: 20px'></i></a>"

        children = get_children(obj.locationtype)
        children_b64 = base64.b64encode(json.dumps(children).encode('ascii')).decode('ascii')

        if obj.locationtype.child:
            ll_act_add = "<a href='#' title='Add Child Location' onclick='loadHierarchyModal(\"" + str(obj.id) + "\", \"" + str(obj.description) + "\", \"" + children_b64 + "\");'><span class='ph ph-plus-square' style='font-size: 20px'></span></a>"
        else:
            ll_act_add = ""

        if root_node:
            ll_act = ll_act_add
        else:
            ll_act = ll_act_edit + ll_act_del + ll_act_add + ll_act_move

        if obj.locationtype.hasclli:
            std_clli = ""
            cust_clli = ""
            if obj.clli:
                std_clli = str(obj.clli.id)
            elif obj.custom_clli:
                cust_clli = obj.custom_clli.clli

            dist = base64.b64encode(json.dumps(obj.calculate_distances(max_entries=10)).encode('ascii')).decode('ascii')
            ll_act += """<a href="#" title="Select Location Code" onclick="loadCLLIModal('""" + str(obj.id) + """', '""" + dist + """', '""" + std_clli + """', '""" + cust_clli + """');"><span class="ph ph-file-code" style='font-size: 20px'></span></a>"""

        ll.append({"id": ll_id,
                   "visible": True,
                   "sortorder": counter,
                   "description": ("&nbsp;" * level) + "<span class='" + ll_icon + "'></span>&nbsp;&nbsp;" + ll_desc,
                   "address": ll_addr,
                   "location_code": ll_code,
                   "actions": ll_act,
                   "DT_RowId": "row_" + ll_id
                   })

        # print(obj, counter, level)
        ltmp, counter = get_locations(LocationHierarchy.objects.filter(parent=obj), counter, level+4)
        # print(obj, len(ltmp), LocationHierarchy.objects.filter(parent=obj))
        ll += ltmp
        if root_node:
            break

    return ll, counter


def api_get_locations(request):
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse([], safe=False)

    locations_list = []
    counter = 0
    level = 0
    hierarchy_locations = LocationHierarchy.objects.filter(tenant=tenant).filter(parent__locationtype__tier=0)
    ll, counter = get_locations(hierarchy_locations, counter, level, root_node=True)
    locations_list += ll
    locations_dict = {"data": locations_list}

    # print(json.dumps(locations_dict, indent=4))
    return JsonResponse({"data": locations_list}, safe=False)


def my_settings(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    action = request.GET.get("action")
    id = request.GET.get("id")
    if request.method == 'POST':
        if action == "addadmin":
            admin_email = request.POST.get("adminEmail")
            aus = AppUser.objects.filter(user__email=admin_email)
            for au in aus:
                au.tenant.add(tenant)
        else:
            ten_name = request.POST.get("tName")
            if ten_name != "":
                tenant.name = ten_name
                tenant.save()
    elif action == "remadmin":
        remadm = AppUser.objects.filter(id=id)
        if len(remadm) == 1:
            if remadm[0].hometenant.id == tenant.id:
                # can't remove admin from their home tenant
                pass
            else:
                remadm[0].tenant.remove(tenant)
                # for remten in remadm[0].tenant.all():
                #     if remten.id == tenant.id:
                #         print(remten)

    admins = tenant.appuser_set.all()

    crumbs = '<li class="breadcrumb-item active">Settings</li>'
    response = render(request, 'home/settings.html', {"baseurl": "http://" + request.get_host() + "/settings", "crumbs": crumbs,
                                                      "tenant": tenant, "global": get_globals(request, tenant),
                                                      "admins": admins})

    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def signup(request):
    # print("signup", request)
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('/tenant')
    else:
        form = SignUpForm()
    return render(request, 'general/signup.html', {'form': form})


class IndexView(TemplateView):
    template_name = "general/index.html"

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/login')
        else:
            return redirect('/home')


class MyLoginView(auth_views.LoginView):
    template_name = "general/login.html"

    def get_success_url(self):
        return reverse('tenant')


class MyLogoutView(auth_views.LogoutView):
    def dispatch(self, request, *args, **kwargs):
        logout(request)
        return redirect('/')


def get_connections(tenant):
    # return PluginModule.objects.filter(Q(tenant=get_default_tenant(obj=True)) | Q(tenant=tenant))
    pm_names = []
    pms = []
    pmlist = PluginModule.objects.filter(tenant=tenant)
    for pm in pmlist:
        pm_names.append(pm.name)
        pms.append(pm)

    pmlist = PluginModule.objects.filter(tenant=get_default_tenant(obj=True))
    for pm in pmlist:
        if pm.name not in pm_names:
            pm_names.append(pm.name)
            pms.append(pm)

    return pms


def exec_func(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    url = request.META['PATH_INFO']         # /exec/meraki/getorgs
    url_list = url.split("/")
    get_mod_name = url_list[-2:][0]
    get_func_name = url_list[-1:][0]
    # logging.error("url_list=" + str(url_list))
    pm = PluginModule.objects.filter(tenant=tenant).filter(name=get_mod_name).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
    if len(pm) == 0:
        pm = PluginModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(name=get_mod_name)
    if len(pm) == 1:
        post_data = json.loads(request.body)
        # logging.error("post_data=" + str(post_data))
        cont_id = post_data["id"]
        if cont_id == "blank":
            cont = None
        else:
            cont = Controller.objects.filter(tenant=tenant).filter(id=cont_id)
            if len(cont) != 1:
                return JsonResponse({"error": "Unable to load Device data."})
        pmn = get_script(pm[0])
        if not pmn:
            return JsonResponse({"error": "Unable to load Plugin Module."})
        globals()[pmn] = __import__(pmn)
        pds = pm[0].devicetype.parmdef
        arg_list = []
        # logging.error("pds=" + str(pds))
        for pd in pds:
            # logging.error("pd=" + str(pd.get("source", "null")))
            # logging.error("func_name=" + str(get_func_name))
            # logging.error("args=" + str(pd.get("args")))
            if pd.get("source", "null") == get_func_name:
                # logging.error("match=True")
                pd_args = pd["args"]
                for pd_a in pd_args:
                    # logging.error("arg=" + str(pd_a))
                    if pd_a == "tenant":
                        arg_list.append(tenant.id)
                    else:
                        pdat = post_data.get(pd_a, "")
                        # logging.error("data=" + str(pdat))
                        if pdat.find("****") >= 0:
                            arg_list.append(cont[0].authparm["api"][pd_a])
                        else:
                            arg_list.append(pdat)

        retval = eval(pmn + "." + get_func_name)(arg_list)
        return JsonResponse(retval, safe=False)
    else:
        return JsonResponse({"error": "Connection Not Defined in Plugin Modules."})


def config_conn(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    url = request.META['PATH_INFO']         # /home/config-int/meraki
    url_list = url.split("/")
    get_mod_name = url_list[-1:][0]
    plugin_id = None
    pm = PluginModule.objects.filter(tenant=tenant).filter(name=get_mod_name).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
    if len(pm) == 0:
        pm = PluginModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(name=get_mod_name)
    if len(pm) == 1:
        plugin_id = pm[0].plugin_id
        pmn = get_script(pm[0])
        # print(plugin_id, pmn)
        if not pmn:
            return HttpResponse("Error: Unable to load Plugin Module.")
        # globals()[pmn] = __import__(pmn)
        # retval = eval(pmn).config_connection(request, tenant_id)
        def_icon = pm[0].default_icon
    else:
        return HttpResponse("Error: Connection Not Defined in Plugin Modules.")

    if request.method == 'POST':
        authdata = {pm[0].devicetype.authtype.name: {}}
        for fld in pm[0].devicetype.parmdef:
            pval = request.POST.get(fld["name"])
            if not pval:
                pval = fld.get("default")
            authdata[pm[0].devicetype.authtype.name][fld["name"]] = pval

        int_id = request.POST.get("connectId")
        if int_id == "blank":
            int_id = ""
        int_desc = request.POST.get("connectDescription")
        cont = None
        if int_id is None or int_id == "":
            cont = Controller.objects.create(name=int_desc, devicetype=pm[0].devicetype, authparm=authdata, tenant=tenant)
            try:
                orgurl = eval(pmn).get_home_link(cont)
            except Exception:
                orgurl = None

            if orgurl:
                HomeLink.objects.create(name=int_desc, url=orgurl, controller=cont, icon_url=def_icon, tenant=tenant)
        else:
            controllers = Controller.objects.filter(tenant=tenant).filter(id=int_id)
            if len(controllers) == 1:
                cont = controllers[0]
                cont.name = int_desc

                ap = cont.authparm
                for fld in pm[0].devicetype.parmdef:
                    fldval = authdata[pm[0].devicetype.authtype.name][fld["name"]]
                    if fldval and fldval.find("****") < 0:
                        ap["api"][fld["name"]] = fldval
                cont.authparm = ap
                print(ap)

                cont.save()
                try:
                    orgurl = eval(pmn).get_home_link(cont)
                except Exception:
                    orgurl = None

                if orgurl:
                    HomeLink.objects.update_or_create(controller=cont, tenant=tenant,
                                                      defaults={"name": int_desc, "url": orgurl, "icon_url": def_icon})

        # call run_on_save if available
        try:
            ros = eval(pmn).run_on_save(request, cont)
        except Exception:
            ros = None


    if request.GET.get("action") == "delobj":
        mer_id = request.GET.get("id")
        Controller.objects.filter(tenant=tenant).filter(id=mer_id).delete()
    elif request.GET.get("action") == "enable":
        mer_id = request.GET.get("id")
        Controller.objects.filter(tenant=tenant).filter(id=mer_id).update(enabled=True)
    elif request.GET.get("action") == "disable":
        mer_id = request.GET.get("id")
        Controller.objects.filter(tenant=tenant).filter(id=mer_id).update(enabled=False)

    dashboards = Controller.objects.filter(tenant=tenant).filter(devicetype=pm[0].devicetype)
    # print(Controller.objects.filter(tenant=tenant))
    print(pm, pm[0].devicetype, Controller.objects.filter(devicetype=pm[0].devicetype))

    crumbs = '<li class="breadcrumb-item">Connect</li><li class="breadcrumb-item active">' + pm[0].description + '</li>'
    response = render(request, "home/config_connection.html", {"crumbs": crumbs,
                                                               "tenant": tenant,
                                                               "mod": pm[0], "data": dashboards,
                                                               "plugin_id": plugin_id,
                                                               "global": get_globals(request, tenant),
                                                               "menuopen": plugin_id, "ddopen": "connect"})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def show_tunnel(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    if request.method == "POST":
        thisid = request.POST.get("objId", None)
        if thisid == "": thisid = None
        desc = request.POST.get("objDesc")
        fqdn = request.POST.get("objUrl")
        TunnelClient.objects.update_or_create(id=thisid, description=desc, tunnelUrl=fqdn, enabled=True, tenant=tenant)

    id = request.GET.get("id")
    action = request.GET.get("action")
    if action == "enable":
        TunnelClient.objects.filter(tenant=tenant).filter(id=id).update(enabled=True)
    elif action == "disable":
        TunnelClient.objects.filter(tenant=tenant).filter(id=id).update(enabled=False)

    tunnels = TunnelClient.objects.filter(tenant=tenant)

    crumbs = '<li class="breadcrumb-item active">Tunnel</li>'
    response = render(request, "home/list_tunnel.html", {"crumbs": crumbs, "tunnels": tunnels,
                                                         "tenant": tenant, "menuopen": "tunnel",
                                                         "global": get_globals(request, tenant)})

    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def show_int(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    intopts = IntegrationModule.objects.filter(Q(tenant=get_default_tenant(obj=True)) | Q(tenant=tenant))
    intconfigs = IntegrationConfiguration.objects.filter(tenant=tenant)
    avail_opts = []
    unavail_opts = []
    for intopt in intopts:
        # pm1_dts = intopt.pm1.devicetype.all()
        # pm2_dts = intopt.pm2.devicetype.all()
        # pm1_cont = Controller.objects.filter(devicetype__in=pm1_dts)
        # pm2_cont = Controller.objects.filter(devicetype__in=pm2_dts)
        if not intopt.pm1 or not intopt.pm2:
            continue
        pm1_cont = Controller.objects.filter(tenant=tenant).filter(devicetype=intopt.pm1.devicetype)
        pm2_cont = Controller.objects.filter(tenant=tenant).filter(devicetype=intopt.pm2.devicetype)
        if len(pm1_cont) > 0 and len(pm2_cont) > 0:
            avail_opts.append(intopt)
        else:
            unavail_opts.append(intopt)

    crumbs = '<li class="breadcrumb-item active">Integrate</li>'
    response = render(request, "home/list_integration.html", {"crumbs": crumbs, "integrations": intconfigs,
                                                              "tenant": tenant, "menuopen": "integrate",
                                                              "avail": avail_opts, "unavail": unavail_opts,
                                                              "global": get_globals(request, tenant)})

    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def config_int(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    if request.method == 'POST':
        modid = request.POST.get("imid")
        objid = request.POST.get("objid")
        postvars = request.POST
        # print(postvars)
        cg1vals = []
        cg2vals = []
        if "cg1" in postvars and "cg2" in postvars:
            cg1vals = [postvars["cg1"]]
            cg2vals = [postvars["cg2"]]
        else:
            for v in postvars:
                if "cg1-" in v:
                    cg1id = v.replace("cg1-", "")
                    cg1vals.append(cg1id)
                if "cg2-" in v:
                    cg2id = v.replace("cg2-", "")
                    cg2vals.append(cg2id)

        if objid:
            ic = IntegrationConfiguration.objects.filter(tenant=tenant).filter(id=objid)[0]
        else:
            ic = IntegrationConfiguration.objects.create(tenant=tenant, integrationmodule_id=modid)
        c1 = Controller.objects.filter(tenant=tenant).filter(id__in=cg1vals)
        ic.pm1.clear()
        ic.pm1.add(*c1)
        c2 = Controller.objects.filter(tenant=tenant).filter(id__in=cg2vals)
        ic.pm2.clear()
        ic.pm2.add(*c2)
        # ic.pm1.add(cg1vals)
        # ic.pm2.add(cg2vals)
        # print(modid, cg1vals, cg2vals)

        return redirect(reverse('show_int'))

    if request.GET.get("action") == "delint":
        intid = request.GET.get("id")
        IntegrationConfiguration.objects.filter(tenant=tenant).filter(id=intid).delete()
        return redirect(reverse('show_int'))
    elif request.GET.get("action") == "addint" or request.GET.get("action") == "editint":
        intid = request.GET.get("id")
        if request.GET.get("action") == "addint":
            intopts = IntegrationModule.objects.filter(tenant=tenant).filter(id=intid)
            if len(intopts) == 0:
                intopts = IntegrationModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(id=intid)
            intopt = intopts[0]
            ic = None
        else:
            ics = IntegrationConfiguration.objects.filter(tenant=tenant).filter(id=intid)
            if len(ics) != 1:
                return redirect(reverse('show_int'))
            ic = ics[0]
            intopt = ic.integrationmodule

        # pm1_dts = intopt.pm1.devicetype.all()
        # pm2_dts = intopt.pm2.devicetype.all()
        # pm1_controllers = Controller.objects.filter(tenant_id=tenant_id).filter(devicetype__in=pm1_dts)
        # pm2_controllers = Controller.objects.filter(tenant_id=tenant_id).filter(devicetype__in=pm2_dts)
        pm1_controllers = Controller.objects.filter(tenant=tenant).filter(devicetype=intopt.pm1.devicetype)
        pm2_controllers = Controller.objects.filter(tenant=tenant).filter(devicetype=intopt.pm2.devicetype)

        crumbs = '<li class="breadcrumb-item"><a href="/home/integrate">Integrate</a></li><li class="breadcrumb-item active">' + intopt.description + '</li>'
        response = render(request, "home/config_integration.html", {"crumbs": crumbs,
                                                                    "tenant": tenant,
                                                                    "m1": pm1_controllers, "m2": pm2_controllers,
                                                                    "intmod": intopt, "intconfig": ic,
                                                                    "global": get_globals(request, tenant)})
        response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
        return response


def status_task(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    time_threshold = timezone.now().replace(hour=0, minute=0, second=0) + timedelta(hours=4)

    if request.user.is_superuser:
        trs = TaskResult.objects.filter(Q(tenant=tenant) | Q(tenant=get_default_tenant(obj=True))).filter(runtime__gt=time_threshold)
    else:
        trs = TaskResult.objects.filter(tenant=tenant).filter(runtime__gt=time_threshold)

    crumbs = '<li class="breadcrumb-item">Status</li><li class="breadcrumb-item active">Task Results</li>'
    response = render(request, "home/status_task.html", {"crumbs": crumbs, "menuopen": "status",
                                                         "tenant": tenant,
                                                         "data": trs,
                                                         "global": get_globals(request, tenant),
                                                         "menuopen": "task-results", "ddopen": "status"})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def config_package(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    if request.GET.get("action") == "delzip":
        intid = request.GET.get("id")
        if request.user.is_superuser:
            UploadZip.objects.filter(Q(tenant=tenant) | Q(tenant=get_default_tenant(obj=True))).\
                filter(id=intid).delete()
        else:
            UploadZip.objects.filter(tenant=tenant).filter(id=intid).delete()

    uploadzip = UploadZip.objects.filter(tenant=tenant)
    uplzip_global = UploadZip.objects.filter(tenant=get_default_tenant(obj=True))

    crumbs = '<li class="breadcrumb-item">Configuration</li><li class="breadcrumb-item active">Packages</li>'
    response = render(request, 'home/packages.html', {"crumbs": crumbs, "tenant": tenant,
                                                      "data": {"zip": uploadzip, "global_zip": uplzip_global},
                                                      "global": get_globals(request, tenant),
                                                      "menuopen": "packages"})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def upload_package(request):
    tenant = get_tenant(request)
    error_text = None
    if not tenant:
        return redirect('/tenant')

    if request.method == 'POST':
        ten_id = request.POST.get("tenant")
        if not ten_id:
            ten_id = str(tenant.id)

        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            print("form valid")
            obj = form.save(commit=False)
            obj.tenant_id = ten_id
            had_error = False
            try:
                obj.save()
            except FileExistsError:
                had_error = True
                error_text = "Error: This package already exists for this Tenant. Please delete the existing package first."

            if not had_error:
                uplfiles = obj.upload_set.all()
                for upl in uplfiles:
                    upl.tenant_id = ten_id
                    upl.save()
                return redirect(reverse("config_package"))
        else:
            print("form invalid")

    form = UploadForm()
    crumbs = '<li class="breadcrumb-item">Configuration</li><li class="breadcrumb-item"><a href="/home/config-package">Packages</a></li><li class="breadcrumb-item active">Upload</li>'
    response = render(request, 'home/upload_package.html', {"crumbs": crumbs, "tenant": tenant, "error": error_text,
                                                            "form": form, "global": get_globals(request, tenant)})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def module_ui(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    url = request.META['PATH_INFO']
    url_list = url.split("/")
    get_mod_name = url_list[-2:][0]
    get_func_name = url_list[-1:][0]
    # print(get_mod_name, get_func_name)
    item_type = None
    if not get_func_name or get_func_name == "":
        return JsonResponse({"error": "Unable to load Plugin Module."})

    if get_mod_name == "plugin":
        pm = PluginModule.objects.filter(tenant=tenant).filter(id=get_func_name)
    else:
        pm = IntegrationModule.objects.filter(tenant=tenant).filter(id=get_func_name)
    if len(pm) == 0:
        if get_mod_name == "plugin":
            item_type = "plugin"
            pm = PluginModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(id=get_func_name)
        else:
            item_type = "integration"
            pm = IntegrationModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(id=get_func_name)

    if len(pm) == 1:
        pmn = get_script(pm[0])
        if not pmn:
            return JsonResponse({"error": "Unable to load Plugin Module."})
        globals()[pmn] = __import__(pmn)
        retval = eval(pmn).do_render(request, tenant)
        templ = get_template(pm[0])
        crumbdesc = retval["desc"]
        del retval["desc"]

        retval["global"] = get_globals(request, tenant)
        crumbs = '<li class="breadcrumb-item">Connect</li><li class="breadcrumb-item active">' + crumbdesc + '</li>'
        retval["crumbs"] = crumbs
        menuopen = get_menu(pm[0], item_type)
        retval["menuopen"] = menuopen
        retval["tenant"] = tenant
        # print(retval)
        response = render(request, templ, retval)
        response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
        return response
    else:
        return HttpResponse("Error: Connection Not Defined in Plugin Modules.")


# def module_ui_test(request):
#     tenant = get_tenant(request)
#     if not tenant:
#         return redirect('/tenant')
#
#     url = request.META['PATH_INFO']         # /home/config-int/meraki
#     url_list = url.split("/")
#     get_mod_name = url_list[-1:][0]
#     pm = PluginModule.objects.filter(name=get_mod_name)
#     if len(pm) == 1:
#         pmn = "scripts." + pm[0].py_mod_name
#         globals()[pmn] = __import__(pmn)
#         retval = eval(pmn).config_connection(request, tenant_id)
#         templ = retval["template"]
#         del retval["template"]
#         crumbdesc = retval["desc"]
#         del retval["desc"]
#
#         retval["tenants"] = tenants
#         retval["tenant_desc"] = tdesc
#         crumbs = '<li class="current">Connect</li><li class="current">' + crumbdesc + '</li>'
#         retval["crumbs"] = crumbs
#         retval["connections"] = get_connections(tenant_id)
#         retval["menuopen"] = "connect"
#         # print(retval)
#
#         return render(request, templ, retval)
#     else:
#         return HttpResponse("Error: Connection Not Defined in Plugin Modules.")


# @csrf_exempt
# def client_tunnel(request):
#     outjson = {}
#     path = request.META['PATH_INFO'].split("/")[-2:]
#     if len(path) == 2:
#         app_str = request.POST.get("app")
#         app_ver = request.POST.get("ver")
#         client_id = path[0]
#         operation = path[1]
#
#         tcs = TunnelClient.objects.filter(clientid=client_id)
#         print(client_id, tcs)
#         if len(tcs) == 1:
#             tc = tcs[0]
#             if operation == "register":
#                 if app_str and app_str != "":
#                     tc.appdesc = str(app_str)
#                 if app_ver and app_ver != "":
#                     tc.appver = str(app_ver)
#                 tc.save()
#                 outjson["portnum"] = tc.tunnelport.portnumber
#             elif operation == "health":
#                 return JsonResponse({"status": "ok"})
#             else:
#                 # t = False
#                 # fmax = 5
#                 # f = 0
#                 # while t is False:
#                 #     # t = make_tunnel_request(inportnum, request.get_json(force=True))
#                 #     t = make_tunnel_request(tc.get_internal_port(), request.POST, request.headers, request.method)
#                 #     time.sleep(1)
#                 #     f += 1
#                 #     if f > fmax:
#                 #         break
#                 t_result, t_response = make_tunnel_request(tc.get_internal_port(), request.POST, request.headers, request.method)
#
#                 if t_result is not False:
#                     resp = t_response.content.decode("UTF-8")
#                     xrt = request.headers.get("X-Return-Type", "raw").lower()
#                     if xrt == "json":
#                         outjson = {"state": "success", "response": json.loads(resp)}
#                         return JsonResponse(outjson)
#                     else:
#                         outjson = {"state": "success", "response": resp}
#                         return JsonResponse(outjson)
#                         # return JsonResponse({"error": str(resp)})
#                 else:
#                     outjson = {"state": "fail", "error": str(t_response)}
#                     return JsonResponse(outjson)
#
#     return JsonResponse(outjson)


def show_devices(request):
    tenant = get_tenant(request)
    error_text = None
    if not tenant:
        return redirect('/tenant')

    crumbs = '<li class="breadcrumb-item active">Devices</li>'
    response = render(request, 'home/devices.html', {"crumbs": crumbs, "tenant": tenant,
                                                     "error": error_text, "menuopen": "devices",
                                                     "global": get_globals(request, tenant)})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def show_subnets(request):
    tenant = get_tenant(request)
    error_text = None
    if not tenant:
        return redirect('/tenant')

    err = None
    context = {}

    if request.method == 'POST':
        subnet_id = request.POST.get("subnet_id")
        desc = request.POST.get("description")
        subnet = request.POST.get("subnet")
        a_scan = request.POST.get("scan")
        if a_scan == "on":
            autoscan = True
        else:
            autoscan = False

        if "/" not in subnet:
            subnet = subnet + "/32"

        sn = None

        try:
            sn = ipaddress.IPv4Network(subnet)
        except Exception as e:
            err = e
            context = {"description": desc, "subnet": subnet, "scan": autoscan}

        if not err:
            if subnet_id == "":
                sn_obj = Subnet.objects.create(subnet=str(sn), tenant=tenant, name=desc, autoscan=autoscan)
                created = True
            else:
                sn_obj, created = Subnet.objects.update_or_create(id=subnet_id, subnet=str(sn), tenant=tenant,
                                                                  defaults={"name": desc, "autoscan": autoscan})
            print(created, sn_obj)

    crumbs = '<li class="breadcrumb-item">IPAM</li><li class="breadcrumb-item active">Subnets</li>'
    response = render(request, 'home/ipam-subnets.html', {"crumbs": crumbs, "tenant": tenant,
                                                     "error": err, "ctx": context, "menuopen": "ipam",
                                                     "global": get_globals(request, tenant)})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


def show_addresses(request):
    tenant = get_tenant(request)
    error_text = None
    if not tenant:
        return redirect('/tenant')

    err = None
    context = {}

    # if request.method == 'POST':
    #     subnet_id = request.POST.get("subnet_id")
    #     desc = request.POST.get("description")
    #     subnet = request.POST.get("subnet")
    #     a_scan = request.POST.get("scan")
    #     if a_scan == "on":
    #         autoscan = True
    #     else:
    #         autoscan = False
    #
    #     if "/" not in subnet:
    #         subnet = subnet + "/32"
    #
    #     sn = None
    #
    #     try:
    #         sn = ipaddress.IPv4Network(subnet)
    #     except Exception as e:
    #         err = e
    #         context = {"description": desc, "subnet": subnet, "scan": autoscan}
    #
    #     if not err:
    #         if subnet_id == "":
    #             sn_obj = Subnet.objects.create(subnet=str(sn), tenant=tenant, name=desc, autoscan=autoscan)
    #             created = True
    #         else:
    #             sn_obj, created = Subnet.objects.update_or_create(id=subnet_id, subnet=str(sn), tenant=tenant,
    #                                                               defaults={"name": desc, "autoscan": autoscan})
    #         print(created, sn_obj)

    sn_id = request.GET.get("subnet")
    sn = Subnet.objects.filter(id=sn_id).first()
    addresses = Address.objects.filter(subnet=sn)

    crumbs = '<li class="breadcrumb-item">IPAM</li><li class="breadcrumb-item"><a href="/home/ipam-subnets">Subnets</a></li><li class="breadcrumb-item active">' + sn.subnet + '</li>'
    response = render(request, 'home/ipam-addresses.html', {"crumbs": crumbs, "tenant": tenant,
                                                            "error": err, "ctx": context, "menuopen": "ipam",
                                                            "global": get_globals(request, tenant),
                                                            "sn": sn, "addr": addresses})
    response.set_cookie(key='tenant_id', value=str(tenant.id), samesite="lax", secure=False)
    return response


class TenantViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class ControllerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Controller.objects.all()
    serializer_class = ControllerSerializer


class IntegrationConfigurationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows integration configurations to be viewed or edited.
    """
    queryset = IntegrationConfiguration.objects.all()
    serializer_class = IntegrationConfigurationSerializer


class IntegrationModuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows integration modules to be viewed or edited.
    """
    queryset = IntegrationModule.objects.all()
    serializer_class = IntegrationModuleSerializer


class PluginModuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows plugin modules to be viewed or edited.
    """
    queryset = PluginModule.objects.all()
    serializer_class = PluginModuleSerializer


class DeviceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

    def get_queryset(self):
        """
        Optionally restricts the returned role types,
        by filtering against a `name` query parameter in the URL.
        """
        queryset = Device.objects.all()
        parm = self.request.query_params.get('serial_number', None)
        if parm is not None:
            queryset = queryset.filter(serial_number__iexact=parm)
        return queryset


class DeviceModelTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = DeviceModelType.objects.all()
    serializer_class = DeviceModelTypeSerializer

    def get_queryset(self):
        """
        Optionally restricts the returned role types,
        by filtering against a `name` query parameter in the URL.
        """
        queryset = DeviceModelType.objects.all()
        parm = self.request.query_params.get('name', None)
        if parm is not None:
            queryset = queryset.filter(name__iexact=parm)
        return queryset


class DeviceTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = DeviceType.objects.all()
    serializer_class = DeviceTypeSerializer


class AuthTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = AuthType.objects.all()
    serializer_class = AuthTypeSerializer


class L1InterfaceTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L1InterfaceType.objects.all()
    serializer_class = L1InterfaceTypeSerializer


class L1InterfaceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L1Interface.objects.all()
    serializer_class = L1InterfaceSerializer


class L1DomainViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L1Domain.objects.all()
    serializer_class = L1DomainSerializer


class L2InterfaceTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L2InterfaceType.objects.all()
    serializer_class = L2InterfaceTypeSerializer


class L2InterfaceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L2Interface.objects.all()
    serializer_class = L2InterfaceSerializer


class L2DomainTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L2DomainType.objects.all()
    serializer_class = L2DomainTypeSerializer


class L2DomainViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L2Domain.objects.all()
    serializer_class = L2DomainSerializer


class L3InterfaceTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L3InterfaceType.objects.all()
    serializer_class = L3InterfaceTypeSerializer


class L3InterfaceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L3Interface.objects.all()
    serializer_class = L3InterfaceSerializer


class L3DomainViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = L3Domain.objects.all()
    serializer_class = L3DomainSerializer


class TunnelClientViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows tunnel clients to be viewed or edited.
    """
    queryset = TunnelClient.objects.all()
    serializer_class = TunnelClientSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        item_id = self.kwargs['pk']
        appuser = AppUser.objects.filter(user=self.request.user).first()
        tenants = Tenant.objects.filter(appuser=appuser)
        # print(tenants)
        return TunnelClient.objects.filter(tenant__in=tenants).filter(id=item_id).first()

    def get_queryset(self):
        appuser = AppUser.objects.filter(user=self.request.user).first()
        tenants = Tenant.objects.filter(appuser=appuser)
        queryset = TunnelClient.objects.filter(tenant__in=tenants)
        parm = self.request.query_params.get('clientid', None)
        if parm is not None:
            queryset = queryset.filter(clientid__iexact=parm)

        return queryset


class TenantAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = Tenant.objects.get(pk=id)
            serializer = TenantSerializer(item)
            return Response(serializer.data)
        except Tenant.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = Tenant.objects.get(pk=id)
        except Tenant.DoesNotExist:
            return Response(status=404)
        serializer = TenantSerializer(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = Tenant.objects.get(pk=id)
        except Tenant.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class TenantAPIListView(APIView):

    def get(self, request, format=None):
        items = Tenant.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = TenantSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = TenantSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class DeviceAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = Device.objects.get(pk=id)
            serializer = DeviceSerializerFlat(item)
            return Response(serializer.data)
        except Device.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = Device.objects.get(pk=id)
        except Device.DoesNotExist:
            return Response(status=404)
        serializer = DeviceSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = Device.objects.get(pk=id)
        except Device.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class DeviceAPIListView(APIView):

    def get(self, request, format=None):
        items = Device.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = DeviceSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = DeviceSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L1InterfaceTypeAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L1InterfaceType.objects.get(pk=id)
            serializer = L1InterfaceTypeSerializerFlat(item)
            return Response(serializer.data)
        except L1InterfaceType.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L1InterfaceType.objects.get(pk=id)
        except L1InterfaceType.DoesNotExist:
            return Response(status=404)
        serializer = L1InterfaceTypeSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L1InterfaceType.objects.get(pk=id)
        except L1InterfaceType.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L1InterfaceTypeAPIListView(APIView):

    def get(self, request, format=None):
        items = L1InterfaceType.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L1InterfaceTypeSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L1InterfaceTypeSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L1InterfaceAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L1Interface.objects.get(pk=id)
            serializer = L1InterfaceSerializerFlat(item)
            return Response(serializer.data)
        except L1Interface.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L1Interface.objects.get(pk=id)
        except L1Interface.DoesNotExist:
            return Response(status=404)
        serializer = L1InterfaceSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L1Interface.objects.get(pk=id)
        except L1Interface.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L1InterfaceAPIListView(APIView):

    def get(self, request, format=None):
        items = L1Interface.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L1InterfaceSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L1InterfaceSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L1DomainAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L1Domain.objects.get(pk=id)
            serializer = L1DomainSerializerFlat(item)
            return Response(serializer.data)
        except L1Domain.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L1Domain.objects.get(pk=id)
        except L1Domain.DoesNotExist:
            return Response(status=404)
        serializer = L1DomainSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L1Domain.objects.get(pk=id)
        except L1Domain.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L1DomainAPIListView(APIView):

    def get(self, request, format=None):
        items = L1Domain.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L1DomainSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L1DomainSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L2InterfaceTypeAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L2InterfaceType.objects.get(pk=id)
            serializer = L2InterfaceTypeSerializerFlat(item)
            return Response(serializer.data)
        except L2InterfaceType.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L2InterfaceType.objects.get(pk=id)
        except L2InterfaceType.DoesNotExist:
            return Response(status=404)
        serializer = L2InterfaceTypeSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L2InterfaceType.objects.get(pk=id)
        except L2InterfaceType.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L2InterfaceTypeAPIListView(APIView):

    def get(self, request, format=None):
        items = L2InterfaceType.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L2InterfaceTypeSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L2InterfaceTypeSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L2InterfaceAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L2Interface.objects.get(pk=id)
            serializer = L2InterfaceSerializerFlat(item)
            return Response(serializer.data)
        except L2Interface.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L2Interface.objects.get(pk=id)
        except L2Interface.DoesNotExist:
            return Response(status=404)
        serializer = L2InterfaceSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L2Interface.objects.get(pk=id)
        except L2Interface.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L2InterfaceAPIListView(APIView):

    def get(self, request, format=None):
        items = L2Interface.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L2InterfaceSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L2InterfaceSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L2DomainTypeAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L2DomainType.objects.get(pk=id)
            serializer = L2DomainTypeSerializerFlat(item)
            return Response(serializer.data)
        except L2DomainType.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L2DomainType.objects.get(pk=id)
        except L2DomainType.DoesNotExist:
            return Response(status=404)
        serializer = L2DomainTypeSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L2DomainType.objects.get(pk=id)
        except L2DomainType.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L2DomainTypeAPIListView(APIView):

    def get(self, request, format=None):
        items = L2DomainType.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L2DomainTypeSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L2DomainTypeSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L2DomainAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L2Domain.objects.get(pk=id)
            serializer = L2DomainSerializerFlat(item)
            return Response(serializer.data)
        except L2Domain.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L2Domain.objects.get(pk=id)
        except L2Domain.DoesNotExist:
            return Response(status=404)
        serializer = L2DomainSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L2Domain.objects.get(pk=id)
        except L2Domain.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L2DomainAPIListView(APIView):

    def get(self, request, format=None):
        items = L2Domain.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L2DomainSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L2DomainSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L3InterfaceTypeAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L3InterfaceType.objects.get(pk=id)
            serializer = L3InterfaceTypeSerializerFlat(item)
            return Response(serializer.data)
        except L3InterfaceType.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L3InterfaceType.objects.get(pk=id)
        except L3InterfaceType.DoesNotExist:
            return Response(status=404)
        serializer = L3InterfaceTypeSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L3InterfaceType.objects.get(pk=id)
        except L3InterfaceType.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L3InterfaceTypeAPIListView(APIView):

    def get(self, request, format=None):
        items = L3InterfaceType.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L3InterfaceTypeSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L3InterfaceTypeSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L3DomainAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L3Domain.objects.get(pk=id)
            serializer = L3DomainSerializerFlat(item)
            return Response(serializer.data)
        except L3Domain.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L3Domain.objects.get(pk=id)
        except L3Domain.DoesNotExist:
            return Response(status=404)
        serializer = L3DomainSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L3Domain.objects.get(pk=id)
        except L3Domain.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L3DomainAPIListView(APIView):

    def get(self, request, format=None):
        items = L3Domain.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L3DomainSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L3DomainSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class L3InterfaceAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = L3Interface.objects.get(pk=id)
            serializer = L3InterfaceSerializerFlat(item)
            return Response(serializer.data)
        except L3Interface.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = L3Interface.objects.get(pk=id)
        except L3Interface.DoesNotExist:
            return Response(status=404)
        serializer = L3InterfaceSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = L3Interface.objects.get(pk=id)
        except L3Interface.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class L3InterfaceAPIListView(APIView):

    def get(self, request, format=None):
        items = L3Interface.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = L3InterfaceSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = L3InterfaceSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class ControllerAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = Controller.objects.get(pk=id)
            serializer = ControllerSerializerFlat(item)
            return Response(serializer.data)
        except Controller.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = Controller.objects.get(pk=id)
        except Controller.DoesNotExist:
            return Response(status=404)
        serializer = ControllerSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = Controller.objects.get(pk=id)
        except Controller.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class ControllerAPIListView(APIView):

    def get(self, request, format=None):
        items = Controller.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = ControllerSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = ControllerSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class DeviceModelTypeAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = DeviceModelType.objects.get(pk=id)
            serializer = DeviceModelTypeSerializerFlat(item)
            return Response(serializer.data)
        except DeviceModelType.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = DeviceModelType.objects.get(pk=id)
        except DeviceModelType.DoesNotExist:
            return Response(status=404)
        serializer = DeviceModelTypeSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = DeviceModelType.objects.get(pk=id)
        except DeviceModelType.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class DeviceModelTypeAPIListView(APIView):

    def get(self, request, format=None):
        items = DeviceModelType.objects.all()
        paginator = PageNumberPagination()
        parm = self.request.query_params.get('name', None)
        if parm is not None:
            items = items.filter(name__iexact=parm)
        result_page = paginator.paginate_queryset(items, request)
        serializer = DeviceModelTypeSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = DeviceModelTypeSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class DeviceTypeAPIView(APIView):

    def get(self, request, id, format=None):
        try:
            item = DeviceType.objects.get(pk=id)
            serializer = DeviceTypeSerializerFlat(item)
            return Response(serializer.data)
        except DeviceType.DoesNotExist:
            return Response(status=404)

    def put(self, request, id, format=None):
        try:
            item = DeviceType.objects.get(pk=id)
        except DeviceType.DoesNotExist:
            return Response(status=404)
        serializer = DeviceModelTypeSerializerFlat(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, id, format=None):
        try:
            item = DeviceType.objects.get(pk=id)
        except DeviceType.DoesNotExist:
            return Response(status=404)
        item.delete()
        return Response(status=204)


class DeviceTypeAPIListView(APIView):

    def get(self, request, format=None):
        items = DeviceType.objects.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(items, request)
        serializer = DeviceTypeSerializerFlat(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = DeviceTypeSerializerFlat(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class UploadZipViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Uploaded ZIP files to be viewed, edited or deleted.

    retrieve:
    Return an Uploaded ZIP File instance.

    list:
    Return all Uploaded ZIP files.
    """
    queryset = UploadZip.objects.all().order_by('description')
    serializer_class = UploadZipSerializer


class UploadViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Uploaded files to be viewed, edited or deleted.

    retrieve:
    Return an Uploaded File instance.

    list:
    Return all Uploaded files.
    """
    queryset = Upload.objects.all().order_by('description')
    serializer_class = UploadSerializer


def export_data(request):
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="somefilename.csv"'},
    )

    writer = csv.writer(response)
    writer.writerow(["manufacturer", "model", "slug", "u_height"])
    dmts = DeviceModelType.objects.all()
    for dmt in dmts:
        writer.writerow(["Cisco", dmt.name, dmt.named_id, dmt.size_rack_u])

    return response
