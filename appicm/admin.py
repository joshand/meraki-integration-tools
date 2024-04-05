from django.contrib import admin
from appicm.models import *
from django_google_maps import widgets as map_widgets
from django_google_maps import fields as map_fields


class L1InterfaceAdmin(admin.ModelAdmin):
    readonly_fields = ('rawdata', )


class ConstructAdmin(admin.ModelAdmin):
    readonly_fields = ('rawdata', )


# class TunnelAdmin(admin.ModelAdmin):
#     readonly_fields = ('rawdata', )


class UploadAdmin(admin.ModelAdmin):
    readonly_fields = ('filedata', 'fspath', 'filename')


class CityStateAdmin(admin.ModelAdmin):
    formfield_overrides = {
        map_fields.AddressField: {'widget': map_widgets.GoogleMapsAddressWidget},
    }


class LocationObjectAdmin(admin.ModelAdmin):
    formfield_overrides = {
        map_fields.AddressField: {'widget': map_widgets.GoogleMapsAddressWidget},
    }

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
admin.site.register(Tunnel)
admin.site.register(IntegrationModule)
admin.site.register(IntegrationConfiguration)
admin.site.register(UploadZip)
admin.site.register(Upload, UploadAdmin)
admin.site.register(CloudImage)
admin.site.register(CloudInstance)
admin.site.register(CloudSecurityGroup)
admin.site.register(CloudSubnet)
admin.site.register(CloudVPC)
admin.site.register(CustomMenu)
admin.site.register(CustomTemplate)
admin.site.register(Operation)
# admin.site.register(TunnelPort)
admin.site.register(TunnelClient)
admin.site.register(CityState, CityStateAdmin)
admin.site.register(Site)       #SiteAdmin
admin.site.register(Floor)
admin.site.register(Room)
admin.site.register(Row)
admin.site.register(Rack)
admin.site.register(CLLI)
admin.site.register(LocationObject, LocationObjectAdmin)
admin.site.register(LocationHierarchy)
admin.site.register(LocationType)
