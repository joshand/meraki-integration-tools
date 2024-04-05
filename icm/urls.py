"""icm URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework import routers
from appicm import views
from rest_framework.schemas import get_schema_view
from rest_framework.renderers import JSONOpenAPIRenderer
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter(trailing_slash=False)
router.register(r'tenants', views.TenantViewSet)
router.register(r'controllers', views.ControllerViewSet)
router.register(r'devicemodeltypes', views.DeviceModelTypeViewSet)
router.register(r'devices', views.DeviceViewSet)
router.register(r'devicetypes', views.DeviceTypeViewSet)
router.register(r'authtypes', views.AuthTypeViewSet)
router.register(r'l1interfacetype', views.L1InterfaceTypeViewSet)
router.register(r'l1interface', views.L1InterfaceViewSet)
router.register(r'l1domain', views.L1DomainViewSet)
router.register(r'l2interfacetype', views.L2InterfaceTypeViewSet)
router.register(r'l2interface', views.L2InterfaceViewSet)
router.register(r'l2domaintype', views.L2DomainTypeViewSet)
router.register(r'l2domain', views.L2DomainViewSet)
router.register(r'l3interfacetype', views.L3InterfaceTypeViewSet)
router.register(r'l3interface', views.L3InterfaceViewSet)
router.register(r'l3domain', views.L3DomainViewSet)
router.register(r'uploadzip', views.UploadZipViewSet)
router.register(r'upload', views.UploadViewSet)
router.register(r'integrationconfigurations', views.IntegrationConfigurationViewSet)
router.register(r'integrationmodules', views.IntegrationModuleViewSet)
router.register(r'pluginmodules', views.PluginModuleViewSet)
# router.register(r'tunnelclients', views.TunnelClientViewSet)

schema_view = get_schema_view(title="Cisco Integration Tools API", renderer_classes=[JSONOpenAPIRenderer])

urlpatterns = [
    path('', views.IndexView.as_view(), name='root'),
    path('admin/', admin.site.urls),
    path('login/', views.MyLoginView.as_view(), name='login'),
    re_path(r'^home/$', views.home, name='home'),
    re_path(r'^settings/$', views.my_settings, name='settings'),
    re_path(r'^tenant/$', views.tenant, name='tenant'),
    path('logout/', views.MyLogoutView.as_view(), name='logout'),
    re_path(r'^signup/$', views.signup, name='signup'),
    # re_path(r'^api/v0/tunnel', views.client_tunnel, name='client_tunnel'),
    path(r'api/v0/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    re_path(r'^home/config-conn', views.config_conn, name='config_conn'),
    re_path(r'^exec', views.exec_func, name='exec_func'),
    re_path(r'^home/tunnel$', views.show_tunnel, name='show_tunnel'),
    re_path(r'^home/integrate$', views.show_int, name='show_int'),
    re_path(r'^home/config-int$', views.config_int, name='config_int'),
    re_path(r'^home/status-task$', views.status_task, name='status_task'),
    re_path(r'^home/config-package$', views.config_package, name='config_package'),
    re_path(r'^home/upload-package$', views.upload_package, name='upload_package'),
    re_path(r'^task/result', views.status_task_result, name='status_task_result'),
    re_path(r'^module', views.module_ui, name='module_ui'),
    re_path(r'^home/settings-sites', views.show_config, name='show_config'),
    re_path(r'^home/settings-layout', views.show_layout, name='show_layout'),
    re_path(r'^api/get-devices', views.api_get_devices, name='get_devices'),

                  # url(r'^api/v0/tenant/(?P<id>[0-9a-f-]+)$', views.TenantAPIView.as_view()),
    # url(r'^api/v0/tenant/$', views.TenantAPIListView.as_view()),
    #
    # url(r'^api/v0/controller/(?P<id>[0-9a-f-]+)$', views.ControllerAPIView.as_view()),
    # url(r'^api/v0/controller/$', views.ControllerAPIListView.as_view()),
    #
    # # url(r'^api/v0/devicemodeltype/(?P<id>[0-9a-f-]+)$', views.DeviceModelTypeAPIView.as_view()),
    # path('api/v0/devicemodeltype/<uuid:id>', views.DeviceModelTypeAPIListView.as_view()),
    # url(r'^api/v0/devicemodeltype/$', views.DeviceModelTypeAPIListView.as_view()),
    #
    # url(r'^api/v0/devicetype/(?P<id>[0-9a-f-]+)$', views.DeviceTypeAPIView.as_view()),
    # url(r'^api/v0/devicetype/$', views.DeviceTypeAPIListView.as_view()),
    #
    # url(r'^api/v0/device/(?P<id>[0-9a-f-]+)$', views.DeviceAPIView.as_view()),
    # # path('api/v0/device/<uuid:id>', views.DeviceAPIView.as_view()),
    # url(r'^api/v0/device/$', views.DeviceAPIListView.as_view()),
    #
    # url(r'^api/v0/l1interfacetype/(?P<id>[0-9a-f-]+)$', views.L1InterfaceTypeAPIView.as_view()),
    # url(r'^api/v0/l1interfacetype/$', views.L1InterfaceTypeAPIListView.as_view()),
    #
    # url(r'^api/v0/l1interface/(?P<id>[0-9a-f-]+)$', views.L1InterfaceAPIView.as_view()),
    # url(r'^api/v0/l1interface/$', views.L1InterfaceAPIListView.as_view()),
    #
    # url(r'^api/v0/l1domain/(?P<id>[0-9a-f-]+)$', views.L1DomainAPIView.as_view()),
    # url(r'^api/v0/l1domain/$', views.L1DomainAPIListView.as_view()),
    #
    # url(r'^api/v0/l2interfacetype/(?P<id>[0-9a-f-]+)$', views.L2InterfaceTypeAPIView.as_view()),
    # url(r'^api/v0/l2interfacetype/$', views.L2InterfaceTypeAPIListView.as_view()),
    #
    # url(r'^api/v0/l2interface/(?P<id>[0-9a-f-]+)$', views.L2InterfaceAPIView.as_view()),
    # url(r'^api/v0/l2interface/$', views.L2InterfaceAPIListView.as_view()),
    #
    # url(r'^api/v0/l2domaintype/(?P<id>[0-9a-f-]+)$', views.L2DomainTypeAPIView.as_view()),
    # url(r'^api/v0/l2domaintype/$', views.L2DomainTypeAPIListView.as_view()),
    #
    # url(r'^api/v0/l2domain/(?P<id>[0-9a-f-]+)$', views.L2DomainAPIView.as_view()),
    # url(r'^api/v0/l2domain/$', views.L2DomainAPIListView.as_view()),
    #
    # url(r'^api/v0/l3interfacetype/(?P<id>[0-9a-f-]+)$', views.L3InterfaceTypeAPIView.as_view()),
    # url(r'^api/v0/l3interfacetype/$', views.L3InterfaceTypeAPIListView.as_view()),
    #
    # url(r'^api/v0/l3domain/(?P<id>[0-9a-f-]+)$', views.L3DomainAPIView.as_view()),
    # url(r'^api/v0/l3domain/$', views.L3DomainAPIListView.as_view()),
    #
    # url(r'^api/v0/l3interface/(?P<id>[0-9a-f-]+)$', views.L3InterfaceAPIView.as_view()),
    # url(r'^api/v0/l3interface/$', views.L3InterfaceAPIListView.as_view()),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
