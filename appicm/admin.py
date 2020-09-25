from django.contrib import admin
from appicm.models import *


class L1InterfaceAdmin(admin.ModelAdmin):
    readonly_fields = ('rawdata', )


class ConstructAdmin(admin.ModelAdmin):
    readonly_fields = ('rawdata', )


class TunnelAdmin(admin.ModelAdmin):
    readonly_fields = ('rawdata', )


class UploadAdmin(admin.ModelAdmin):
    readonly_fields = ('filedata', 'fspath', 'filename')


admin.site.register(Tenant)
admin.site.register(AppUser)
admin.site.register(Controller)
admin.site.register(DeviceModelType)
admin.site.register(Device)
admin.site.register(DeviceType)
admin.site.register(AuthType)
admin.site.register(L1InterfaceType)
admin.site.register(L1Interface, L1InterfaceAdmin)
admin.site.register(L1Domain)
admin.site.register(L2InterfaceType)
admin.site.register(L2Interface)
admin.site.register(L2DomainType)
admin.site.register(L2Domain)
admin.site.register(L3InterfaceType)
admin.site.register(L3Domain)
admin.site.register(L3Interface)
admin.site.register(ManagementInterface)
admin.site.register(Module)
admin.site.register(SubModule)
admin.site.register(PDUOutlet)
admin.site.register(TerminalLine)
admin.site.register(ElementConnection)
admin.site.register(TaskResult)
admin.site.register(HomeLink)
admin.site.register(PluginModule)
admin.site.register(Construct, ConstructAdmin)
admin.site.register(Tunnel, TunnelAdmin)
admin.site.register(IntegrationModule)
admin.site.register(IntegrationConfiguration)
admin.site.register(UploadZip)
admin.site.register(Upload, UploadAdmin)
