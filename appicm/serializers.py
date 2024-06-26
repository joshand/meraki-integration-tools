from rest_framework import serializers
from appicm.models import *
from django.forms import ValidationError


class ShowTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ('id', 'name')


class TunnelClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = TunnelClient
        fields = ('id', 'description', 'tunnelUrl', 'tenant', 'enabled')


class ShowDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id', 'name', 'devicetype')


class ShowDeviceModelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id', 'name')


class ShowAuthTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthType
        fields = ('id', 'name')


class ShowDeviceTypeSerializer(serializers.ModelSerializer):
    authtype = ShowAuthTypeSerializer(many=False)

    class Meta:
        model = DeviceType
        fields = ('id', 'name', 'defaultmgmtaddress', 'authtype')


class ShowControllerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Controller
        fields = ('id', 'name')


class ShowL1InterfaceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = L1InterfaceType
        fields = ('id', 'name')


class ShowL1InterfaceSerializer(serializers.ModelSerializer):
    device = ShowDeviceSerializer(many=False)

    class Meta:
        model = L1Interface
        fields = ('id', 'name', 'device')


class ShowL2InterfaceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = L2InterfaceType
        fields = ('id', 'name')


class ShowL2InterfaceSerializer(serializers.ModelSerializer):

    class Meta:
        model = L2Interface
        fields = ('id', 'number', 'name')


class ShowL2DomainTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = L2DomainType
        fields = ('id', 'name')


class ShowL3InterfaceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = L3InterfaceType
        fields = ('id', 'name')


class ShowL3DomainSerializer(serializers.ModelSerializer):

    class Meta:
        model = L3Domain
        fields = ('id', 'name')


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ('id', 'name')


class AuthTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = DeviceType
        depth = 2
        fields = ('id', 'name', 'tenant')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = Device.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        instance.save()
        return instance


class DeviceModelTypeSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = DeviceModelType
        fields = ('id', 'name', 'tenant')


class DeviceModelTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = DeviceModelType
        fields = ('id', 'name', 'tenant')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = Device.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        instance.save()
        return instance


class DeviceTypeSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = DeviceType
        fields = ('id', 'name', 'defaultmgmtaddress', 'tenant', 'authtype')


class DeviceTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    authtype = ShowAuthTypeSerializer(many=False)

    class Meta:
        model = DeviceType
        depth = 2
        fields = ('id', 'name', 'defaultmgmtaddress', 'tenant', 'authtype')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        authtypes_data = validated_data.pop('authtype')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in AuthType.objects.filter(name__iexact=authtypes_data["name"]):
            validated_data["authtype"] = t
            break
        sdata = Device.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        authtypes_data = validated_data.pop('authtype')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in AuthType.objects.filter(name__iexact=authtypes_data["name"]):
            instance.authtype = t
            break
        instance.save()
        return instance


class ControllerSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = Controller
        fields = ('id', 'name', 'authparm', 'mgmtaddress', 'tenant', 'devicetype')


class ControllerSerializer(serializers.ModelSerializer):
    tenant_detail = ShowTenantSerializer(source='tenant', many=False, read_only=True)
    devicetype_detail = ShowDeviceTypeSerializer(source='devicetype', many=False, read_only=True)
    devicetype = serializers.CharField()
    # tenant = serializers.UUIDField()

    class Meta:
        model = Controller
        fields = ('id', 'name', 'authparm', 'mgmtaddress', 'tenant', 'devicetype', 'tenant_detail', 'devicetype_detail')
        read_only_fields = ('tenant', 'devicetype')

    def get_devicetype(self, obj):
        return str(obj.id)

    def to_representation(self, instance):
        data = super(ControllerSerializer, self).to_representation(instance)
        data['devicetype'] = self.get_devicetype(instance)
        return data

    def validate(self, data):
        """
        set tenantid and devicetype
        """
        user = None
        tenant = None
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
            tenant = user.appuser.hometenant

        if user:
            dts = DeviceType.objects.filter(tenant_id=str(tenant.id)).filter(name=data["devicetype"])
            if len(dts) <= 0:
                dts = DeviceType.objects.filter(tenant_id=get_default_tenant()).filter(name=data["devicetype"])

            if len(dts) > 0:
                data["devicetype"] = dts[0]
                data["tenant"] = tenant

        return data

    def __init__(self, *args, **kwargs):
        super(ControllerSerializer, self).__init__(*args, **kwargs)
        if "context" in kwargs:
            request = kwargs['context']['request']
            include_detail = request.GET.get('detail', "false")
            if include_detail.lower() == "false":
                self.fields.pop("tenant_detail")
                self.fields.pop("devicetype_detail")


class PluginModuleSerializer(serializers.ModelSerializer):
    tenant_detail = ShowTenantSerializer(source='tenant', many=False, read_only=True)
    devicetype_detail = ShowDeviceTypeSerializer(source='devicetype', many=False, read_only=True)

    class Meta:
        model = PluginModule
        fields = ('id', 'name', 'description', 'entity_name', 'entity_name_plural', 'sync_interval', 'default_icon', 'tenant', 'devicetype', 'tenant_detail', 'devicetype_detail')

    def __init__(self, *args, **kwargs):
        super(PluginModuleSerializer, self).__init__(*args, **kwargs)
        if "context" in kwargs:
            request = kwargs['context']['request']
            include_detail = request.GET.get('detail', "false")
            if include_detail.lower() == "false":
                self.fields.pop("tenant_detail")
                self.fields.pop("devicetype_detail")


class IntegrationModuleSerializer(serializers.ModelSerializer):
    tenant_detail = ShowTenantSerializer(source='tenant', many=False, read_only=True)
    pm1_detail = PluginModuleSerializer(source='pm1', many=False, read_only=True)
    pm2_detail = PluginModuleSerializer(source='pm2', many=False, read_only=True)

    class Meta:
        model = IntegrationModule
        fields = ('id', 'name', 'description', 'notes', 'sync_interval', 'is_multi_select', 'tenant', 'pm1', 'pm2', 'tenant_detail', 'pm1_detail', 'pm2_detail')

    def __init__(self, *args, **kwargs):
        super(IntegrationModuleSerializer, self).__init__(*args, **kwargs)
        if "context" in kwargs:
            request = kwargs['context']['request']
            include_detail = request.GET.get('detail', "false")
            if include_detail.lower() == "false":
                self.fields.pop("tenant_detail")
                self.fields.pop("pm1_detail")
                self.fields.pop("pm2_detail")


class IntegrationConfigurationSerializer(serializers.ModelSerializer):
    tenant_detail = ShowTenantSerializer(source='tenant', many=False, read_only=True)
    integrationmodule_detail = IntegrationModuleSerializer(source='integrationmodule', many=False, read_only=True)
    pm1_detail = ControllerSerializer(source='pm1', many=True, read_only=True)
    pm2_detail = ControllerSerializer(source='pm2', many=True, read_only=True)
    integrationmodule = serializers.CharField()

    class Meta:
        model = IntegrationConfiguration
        fields = ('id', 'tenant', 'integrationmodule', 'pm1', 'pm2', 'tenant_detail', 'integrationmodule_detail', 'pm1_detail', 'pm2_detail')

    def get_integrationmodule(self, obj):
        return str(obj.id)

    def to_representation(self, instance):
        data = super(IntegrationConfigurationSerializer, self).to_representation(instance)
        data['integrationmodule'] = self.get_integrationmodule(instance)
        return data

    def validate(self, data):
        """
        set tenantid and devicetype
        """
        user = None
        tenant = None
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
            tenant = user.appuser.hometenant

        if user:
            ims = IntegrationModule.objects.filter(tenant_id=str(tenant.id)).filter(name=data["integrationmodule"])
            if len(ims) <= 0:
                ims = IntegrationModule.objects.filter(tenant_id=get_default_tenant()).filter(name=data["integrationmodule"])

            if len(ims) > 0:
                data["integrationmodule"] = ims[0]
                data["tenant"] = tenant

        return data

    def __init__(self, *args, **kwargs):
        super(IntegrationConfigurationSerializer, self).__init__(*args, **kwargs)
        if "context" in kwargs:
            request = kwargs['context']['request']
            include_detail = request.GET.get('detail', "false")
            if include_detail.lower() == "false":
                self.fields.pop("tenant_detail")
                self.fields.pop("integrationmodule_detail")
                self.fields.pop("pm1_detail")
                self.fields.pop("pm2_detail")


class DeviceSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id', 'name', 'serial_number', 'authparm', 'mgmtaddress', 'tenant', 'devicetype', 'controller', 'devicemodeltype')


class DeviceSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    devicetype = ShowDeviceTypeSerializer(many=False)
    controller = ShowControllerSerializer(many=False)
    devicemodeltype = ShowDeviceModelTypeSerializer(many=False)

    class Meta:
        model = Device
        depth = 2
        fields = ('id', 'name', 'serial_number', 'authparm', 'mgmtaddress', 'tenant', 'devicetype', 'controller', 'devicemodeltype')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        devicetypes_data = validated_data.pop('devicetype')
        controllers_data = validated_data.pop('controller')
        devicemodeltypes_data = validated_data.pop('devicemodeltype')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in DeviceType.objects.filter(name__iexact=devicetypes_data["name"]):
            validated_data["devicetype"] = t
            break
        for t in Controller.objects.filter(name__iexact=controllers_data["name"]):
            validated_data["controller"] = t
            break
        for t in DeviceModelType.objects.filter(name__iexact=controllers_data["name"]):
            validated_data["devicemodeltype"] = t
            break
        sdata = Device.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        devicetypes_data = validated_data.pop('devicetype')
        controllers_data = validated_data.pop('controller')
        devicemodeltypes_data = validated_data.pop('devicemodeltype')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in DeviceType.objects.filter(name__iexact=devicetypes_data["name"]):
            instance.devicetype = t
            break
        for t in Controller.objects.filter(name__iexact=controllers_data["name"]):
            instance.controller = t
            break
        for t in DeviceModelType.objects.filter(name__iexact=controllers_data["name"]):
            instance.devicemodeltype = t
            break
        instance.save()
        return instance


class L1InterfaceTypeSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L1InterfaceType
        fields = ('id', 'name', 'description', 'tenant')


class L1InterfaceTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = L1InterfaceType
        depth = 2
        fields = ('id', 'name', 'description', 'tenant')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = L1InterfaceType.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        instance.save()
        return instance


class L1InterfaceSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L1Interface
        fields = ('id', 'name', 'tenant', 'l1interfacetype', 'device')


class L1InterfaceSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    l1interfacetype = ShowL1InterfaceTypeSerializer(many=False)
    device = ShowDeviceSerializer(many=False)

    class Meta:
        model = L1Interface
        depth = 2
        fields = ('id', 'name', 'tenant', 'l1interfacetype', 'device')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        l1interfacetypes_data = validated_data.pop('l1interfacetype')
        devices_data = validated_data.pop('device')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in L1InterfaceType.objects.filter(name__iexact=l1interfacetypes_data["name"]):
            validated_data["l1interfacetype"] = t
            break
        for t in Device.objects.filter(name__iexact=devices_data["name"]):
            validated_data["device"] = t
            break
        sdata = L1Interface.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        l1interfacetypes_data = validated_data.pop('l1interfacetype')
        devices_data = validated_data.pop('device')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in L1InterfaceType.objects.filter(name__iexact=l1interfacetypes_data["name"]):
            instance.l1interfacetype = t
            break
        for t in Device.objects.filter(name__iexact=devices_data["name"]):
            instance.device = t
            break
        instance.save()
        return instance


class L1DomainSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L1Domain
        fields = ('id', 'tenant', 'l1interfacea', 'l1interfaceb')


class L1DomainSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    l1interfacea = ShowL1InterfaceSerializer(many=False)
    l1interfaceb = ShowL1InterfaceSerializer(many=False)

    class Meta:
        model = L1Domain
        depth = 2
        fields = ('id', 'tenant', 'l1interfacea', 'l1interfaceb')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        l1interfaceas_data = validated_data.pop('l1interfacea')
        l1interfacebs_data = validated_data.pop('l1interfaceb')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break

        devicea = None
        for t in Device.objects.filter(name__iexact=l1interfaceas_data["device"]["name"]):
            devicea = t.id
            break
        if devicea:
            for t in L1Interface.objects.filter(name__iexact=l1interfaceas_data["name"]).filter(device__id=devicea):
                validated_data["l1interfacea"] = t
                break

        deviceb = None
        for t in Device.objects.filter(name__iexact=l1interfacebs_data["device"]["name"]):
            deviceb = t.id
            break
        if deviceb:
            for t in L1Interface.objects.filter(name__iexact=l1interfacebs_data["name"]).filter(device__id=deviceb):
                validated_data["l1interfaceb"] = t
                break

        # print(devicea, deviceb, validated_data, l1interfaceas_data["name"], l1interfacebs_data["name"])
        sdata = L1Domain.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        l1interfaceas_data = validated_data.pop('l1interfacea')
        l1interfacebs_data = validated_data.pop('l1interfaceb')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break

        devicea = None
        for t in Device.objects.filter(name__iexact=l1interfaceas_data["device"]["name"]):
            devicea = t.id
            break
        if devicea:
            for t in L1Interface.objects.filter(name__iexact=l1interfaceas_data["name"]).filter(device__id=devicea):
                instance.l1interfacea = t
                break

        deviceb = None
        for t in Device.objects.filter(name__iexact=l1interfacebs_data["device"]["name"]):
            deviceb = t.id
            break
        if deviceb:
            for t in L1Interface.objects.filter(name__iexact=l1interfacebs_data["name"]).filter(device__id=deviceb):
                instance.l1interfaceb = t
                break

        instance.save()
        return instance


class L2InterfaceTypeSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L2InterfaceType
        fields = ('id', 'name', 'tenant')


class L2InterfaceTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = L2InterfaceType
        depth = 2
        fields = ('id', 'name', 'tenant')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = L2InterfaceType.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        instance.save()
        return instance


class L2InterfaceSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L2Interface
        fields = ('id', 'number', 'name', 'tenant', 'l2interfacetype')


class L2InterfaceSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    l2interfacetype = ShowL2InterfaceTypeSerializer(many=False)
    # device = ShowDeviceSerializer(many=False)

    class Meta:
        model = L2Interface
        depth = 2
        fields = ('id', 'number', 'name', 'tenant', 'l2interfacetype')   # , 'device'

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        l2interfacetypes_data = validated_data.pop('l2interfacetype')
        # devices_data = validated_data.pop('device')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in L2InterfaceType.objects.filter(name__iexact=l2interfacetypes_data["name"]):
            validated_data["l2interfacetype"] = t
            break
        # for t in Device.objects.filter(name__iexact=devices_data["name"]):
        #     validated_data["device"] = t
        #     break
        sdata = L2Interface.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        l2interfacetypes_data = validated_data.pop('l2interfacetype')
        # devices_data = validated_data.pop('device')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in L2InterfaceType.objects.filter(name__iexact=l2interfacetypes_data["name"]):
            instance.l2interfacetype = t
            break
        # for t in Device.objects.filter(name__iexact=devices_data["name"]):
        #     instance.device = t
        #     break
        instance.save()
        return instance


class L2DomainTypeSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L2DomainType
        fields = ('id', 'name', 'tenant')


class L2DomainTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = L2DomainType
        depth = 2
        fields = ('id', 'name', 'tenant')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = L2DomainType.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        instance.save()
        return instance


class L2DomainSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L2Domain
        fields = ('id', 'allowedrange', 'tenant', 'l2domaintype', 'l2interface', 'l1interface')


class L2DomainSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    l2domaintype = ShowL2DomainTypeSerializer(many=False)
    l2interface = ShowL2InterfaceSerializer(many=False)
    l1interface = ShowL1InterfaceSerializer(many=False)

    class Meta:
        model = L2Domain
        depth = 2
        fields = ('id', 'allowedrange', 'tenant', 'l2domaintype', 'l2interface', 'l1interface')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        l2domaintypes_data = validated_data.pop('l2domaintype')
        l2interfaces_data = validated_data.pop('l2interface')
        l1interfaces_data = validated_data.pop('l1interface')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in L2DomainType.objects.filter(name__iexact=l2domaintypes_data["name"]):
            validated_data["l2domaintype"] = t
            break
        for t in L2Interface.objects.filter(name__iexact=l2interfaces_data["name"]):
            validated_data["l2interface"] = t
            break

        devicea = None
        for t in Device.objects.filter(name__iexact=l1interfaces_data["device"]["name"]):
            devicea = t.id
            break
        if devicea:
            for t in L1Interface.objects.filter(name__iexact=l1interfaces_data["name"]).filter(device__id=devicea):
                validated_data["l1interface"] = t
                break

        print(devicea, validated_data)

        sdata = L2Domain.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        l2domaintypes_data = validated_data.pop('l2domaintype')
        l2interfaces_data = validated_data.pop('l2interface')
        l1interfaces_data = validated_data.pop('l1interface')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in L2DomainType.objects.filter(name__iexact=l2domaintypes_data["name"]):
            instance.l2domaintype = t
            break
        for t in L2Interface.objects.filter(name__iexact=l2interfaces_data["name"]):
            instance.l2interface = t
            break

        devicea = None
        for t in Device.objects.filter(name__iexact=l1interfaces_data["device"]["name"]):
            devicea = t.id
            break
        if devicea:
            for t in L1Interface.objects.filter(name__iexact=l1interfaces_data["name"]).filter(device__id=devicea):
                instance.l1interface = t
                break
        instance.save()
        return instance


class L3InterfaceTypeSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L3InterfaceType
        fields = ('id', 'name', 'tenant')


class L3InterfaceTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = L3InterfaceType
        depth = 2
        fields = ('id', 'name', 'tenant')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = L3InterfaceType.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        instance.save()
        return instance


class L3DomainSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L3Domain
        fields = ('id', 'name', 'tenant', 'device')


class L3DomainSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    device = ShowDeviceSerializer(many=True, required=False)

    class Meta:
        model = L3Domain
        depth = 2
        fields = ('id', 'name', 'tenant', 'device')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        devices_data = validated_data.pop('device')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        sdata = L3Domain.objects.create(**validated_data)
        for r in devices_data:
            for t in Device.objects.filter(name__iexact=r["name"]):
                sdata.device.add(t)
                break
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        devices_data = validated_data.pop('device')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for r in devices_data:
            for t in Device.objects.filter(name__iexact=r["name"]):
                instance.device.add(t)
                break
        instance.save()
        return instance


class L3InterfaceSerializerFlat(serializers.ModelSerializer):
    class Meta:
        model = L3Interface
        fields = ('id', 'ipaddress', 'mask', 'tenant', 'device', 'l3interfacetype', 'l2interface', 'l3domain')


class L3InterfaceSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    device = ShowDeviceSerializer(many=False)
    l3interfacetype = ShowL3InterfaceTypeSerializer(many=False)
    l2interface = ShowL2InterfaceSerializer(many=False)
    l3domain = ShowL3DomainSerializer(many=False)

    class Meta:
        model = L3Interface
        depth = 2
        fields = ('id', 'ipaddress', 'mask', 'tenant', 'device', 'l3interfacetype', 'l2interface', 'l3domain')

    def create(self, validated_data):
        print(validated_data)
        tenants_data = validated_data.pop('tenant')
        devices_data = validated_data.pop('device')
        l3interfacetypes_data = validated_data.pop('l3interfacetype')
        l2interfaces_data = validated_data.pop('l2interface')
        l3domains_data = validated_data.pop('l3domain')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in Device.objects.filter(name__iexact=devices_data["name"]):
            validated_data["device"] = t
            break
        for t in L3InterfaceType.objects.filter(name__iexact=l3interfacetypes_data["name"]):
            validated_data["l3interfacetype"] = t
            break
        for t in L2Interface.objects.filter(name__iexact=l2interfaces_data["name"]):
            validated_data["l2interface"] = t
            break
        for t in L3Domain.objects.filter(name__iexact=l3domains_data["name"]):
            validated_data["l3domain"] = t
            break

        print(validated_data)
        sdata = L3Interface.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        devices_data = validated_data.pop('device')
        l3interfacetypes_data = validated_data.pop('l3interfacetype')
        l2interfaces_data = validated_data.pop('l2interface')
        l3domains_data = validated_data.pop('l3domain')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in Device.objects.filter(name__iexact=devices_data["name"]):
            instance.device = t
            break
        for t in L3InterfaceType.objects.filter(name__iexact=l3interfacetypes_data["name"]):
            instance.l3interfacetype = t
            break
        for t in L2Interface.objects.filter(name__iexact=l2interfaces_data["name"]):
            instance.l2interface = t
            break
        for t in L3Domain.objects.filter(name__iexact=l3domains_data["name"]):
            instance.l3domain = t
            break
        instance.save()
        return instance


class UploadZipSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadZip
        fields = ('id', 'description', 'file', 'tenant', 'uploaded_at')


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Upload
        fields = ('id', 'description', 'file', 'filename', 'tenant', 'uploaded_at')

#
# class TunnelClientSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = TunnelClient
#         fields = ('id', 'tunnelport', 'clientid', 'appdesc', 'appver')
