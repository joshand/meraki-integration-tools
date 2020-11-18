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
from datetime import timedelta
from django.utils import timezone
from .forms import UploadForm
from scripts.common import get_script, get_template, get_menu
from rest_framework import status
import logging
from django.forms import model_to_dict


@xframe_options_exempt
def status_task_result(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    taskid = request.META['PATH_INFO'].split("/")[-1:][0]
    trs = TaskResult.objects.filter(tenant=tenant).filter(id=taskid)
    if len(trs) == 1:
        return JsonResponse({"data": trs[0].result.replace("\n", "<br>")})
    else:
        return JsonResponse({"data": "Error loading results."})


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

    crumbs = '<li class="current">Home</li>'
    response = render(request, 'home/home.html', {"baseurl": "http://" + request.get_host() + "/home", "crumbs": crumbs,
                                                  "tenant": tenant, "global": get_globals(request, tenant),
                                                  "homelinks": homelinks})

    response.set_cookie(key='tenant_id', value=str(tenant.id))
    return response


def settings(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    crumbs = '<li class="current">Settings</li>'
    response = render(request, 'home/settings.html', {"baseurl": "http://" + request.get_host() + "/settings", "crumbs": crumbs,
                                                      "tenant": tenant, "global": get_globals(request, tenant)})

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
    return PluginModule.objects.filter(Q(tenant=get_default_tenant(obj=True)) | Q(tenant=tenant))


def exec_func(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    url = request.META['PATH_INFO']         # /exec/meraki/getorgs
    url_list = url.split("/")
    get_mod_name = url_list[-2:][0]
    get_func_name = url_list[-1:][0]
    pm = PluginModule.objects.filter(tenant=tenant).filter(name=get_mod_name)
    if len(pm) == 0:
        pm = PluginModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(name=get_mod_name)
    if len(pm) == 1:
        post_data = json.loads(request.body)
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
        for pd in pds:
            if pd.get("source", "null") == get_func_name:
                pd_args = pd["args"]
                for pd_a in pd_args:
                    pdat = post_data.get(pd_a, "")
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
    pm = PluginModule.objects.filter(tenant=tenant).filter(name=get_mod_name)
    if len(pm) == 0:
        pm = PluginModule.objects.filter(tenant=get_default_tenant(obj=True)).filter(name=get_mod_name)
    if len(pm) == 1:
        pmn = get_script(pm[0])
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

        int_id = request.POST.get("objId")
        if int_id == "blank":
            int_id = ""
        int_desc = request.POST.get("objDesc")
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
                    if fldval.find("****") < 0:
                        ap["api"][fld["name"]] = fldval
                cont.authparm = ap

                cont.save()
                orgurl = eval(pmn).get_home_link(cont)
                HomeLink.objects.update_or_create(controller=cont, tenant=tenant,
                                                  defaults={"name": int_desc, "url": orgurl, "icon_url": def_icon})

    if request.GET.get("action") == "delobj":
        mer_id = request.GET.get("id")
        Controller.objects.filter(tenant=tenant).filter(id=mer_id).delete()

    dashboards = Controller.objects.filter(tenant=tenant).filter(devicetype=pm[0].devicetype)

    crumbs = '<li class="current">Connect</li><li class="current">' + pm[0].description + '</li>'
    return render(request, "home/config_connection.html", {"crumbs": crumbs, "menuopen": "connect",
                                                           "tenant": tenant,
                                                           "mod": pm[0], "data": dashboards,
                                                           "global": get_globals(request, tenant)})


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

    crumbs = '<li class="current">Integrate</li>'
    return render(request, "home/list_integration.html", {"crumbs": crumbs, "integrations": intconfigs,
                                                          "tenant": tenant,
                                                          "avail": avail_opts, "unavail": unavail_opts,
                                                          "global": get_globals(request, tenant)})


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

        crumbs = '<li><a href="/home/integrate">Integrate</a></li><li class="current">' + intopt.description + '</li>'
        return render(request, "home/config_integration.html", {"crumbs": crumbs,
                                                                "tenant": tenant,
                                                                "m1": pm1_controllers, "m2": pm2_controllers,
                                                                "intmod": intopt, "intconfig": ic,
                                                                "global": get_globals(request, tenant)})


def status_task(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    time_threshold = timezone.now().replace(hour=0, minute=0, second=0) + timedelta(hours=4)

    trs = TaskResult.objects.filter(tenant=tenant).filter(runtime__gt=time_threshold)
    crumbs = '<li>Status</li><li class="current">Task Results</li>'
    return render(request, "home/status_task.html", {"crumbs": crumbs, "menuopen": "status",
                                                     "tenant": tenant,
                                                     "data": trs,
                                                     "global": get_globals(request, tenant)})


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

    crumbs = '<li class="current">Configuration</li><li class="current">Packages</li>'
    return render(request, 'home/packages.html', {"crumbs": crumbs, "tenant": tenant,
                                                  "data": {"zip": uploadzip, "global_zip": uplzip_global},
                                                  "global": get_globals(request, tenant)})


def upload_package(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('/tenant')

    if request.method == 'POST':
        ten_id = request.POST.get("tenant")
        if not ten_id:
            ten_id = str(tenant.id)

        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant_id = ten_id
            obj.save()
            uplfiles = obj.upload_set.all()
            for upl in uplfiles:
                upl.tenant_id = ten_id
                upl.save()
            return redirect(reverse("config_package"))

    form = UploadForm()
    crumbs = '<li class="current">Configuration</li><li><a href="/home/config-package">Packages</a></li><li class="current">Upload</li>'
    return render(request, 'home/upload_package.html', {"crumbs": crumbs, "tenant": tenant,
                                                        "form": form, "global": get_globals(request, tenant)})


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
        crumbs = '<li class="current">Connect</li><li class="current">' + crumbdesc + '</li>'
        retval["crumbs"] = crumbs
        menuopen = get_menu(pm[0], item_type)
        retval["menuopen"] = menuopen
        retval["tenant"] = tenant
        # print(retval)
        return render(request, templ, retval)
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
