from rest_framework import serializers
from appicm.models import *
from scripts.tasks import run as task_refresh


class ShowTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ('id', 'url', 'name')


class ShowDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id', 'url', 'name', 'devicetype')


class ShowDeviceModelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id', 'url', 'name')


class ShowAuthTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthType
        fields = ('id', 'url', 'name')


class ShowDeviceTypeSerializer(serializers.ModelSerializer):
    authtype = ShowAuthTypeSerializer(many=False)

    class Meta:
        model = DeviceType
        fields = ('id', 'url', 'name', 'defaultmgmtaddress', 'py_mod_name', 'authtype')


class ShowControllerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Controller
        fields = ('id', 'url', 'name')


class ShowL1InterfaceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = L1InterfaceType
        fields = ('id', 'url', 'name')


class ShowL1InterfaceSerializer(serializers.ModelSerializer):
    device = ShowDeviceSerializer(many=False)

    class Meta:
        model = L1Interface
        fields = ('id', 'url', 'name', 'device')


class ShowL2InterfaceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = L2InterfaceType
        fields = ('id', 'url', 'name')


class ShowL2InterfaceSerializer(serializers.ModelSerializer):

    class Meta:
        model = L2Interface
        fields = ('id', 'url', 'number', 'name')


class ShowL2DomainTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = L2DomainType
        fields = ('id', 'url', 'name')


class ShowL3InterfaceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = L3InterfaceType
        fields = ('id', 'url', 'name')


class ShowL3DomainSerializer(serializers.ModelSerializer):

    class Meta:
        model = L3Domain
        fields = ('id', 'url', 'name')


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ('id', 'url', 'name')


class AuthTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)

    class Meta:
        model = DeviceType
        depth = 2
        fields = ('id', 'url', 'name', 'tenant')

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
        fields = ('id', 'url', 'name', 'tenant')

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
        fields = ('id', 'name', 'py_mod_name', 'defaultmgmtaddress', 'tenant', 'authtype')


class DeviceTypeSerializer(serializers.ModelSerializer):
    tenant = ShowTenantSerializer(many=False)
    authtype = ShowAuthTypeSerializer(many=False)

    class Meta:
        model = DeviceType
        depth = 2
        fields = ('id', 'url', 'name', 'py_mod_name', 'defaultmgmtaddress', 'tenant', 'authtype')

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
    tenant = ShowTenantSerializer(many=False)
    devicetype = ShowDeviceTypeSerializer(many=False)

    class Meta:
        model = Device
        depth = 2
        fields = ('id', 'url', 'name', 'authparm', 'mgmtaddress', 'tenant', 'devicetype')

    def create(self, validated_data):
        tenants_data = validated_data.pop('tenant')
        devicetypes_data = validated_data.pop('devicetype')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            validated_data["tenant"] = t
            break
        for t in DeviceType.objects.filter(name__iexact=devicetypes_data["name"]):
            validated_data["devicetype"] = t
            break
        sdata = Device.objects.create(**validated_data)
        return sdata

    def update(self, instance, validated_data):
        tenants_data = validated_data.pop('tenant')
        devicetypes_data = validated_data.pop('devicetype')
        for t in Tenant.objects.filter(name__iexact=tenants_data["name"]):
            instance.tenant = t
            break
        for t in DeviceType.objects.filter(name__iexact=devicetypes_data["name"]):
            instance.devicetype = t
            break
        instance.save()
        return instance


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
        fields = ('id', 'url', 'name', 'serial_number', 'authparm', 'mgmtaddress', 'tenant', 'devicetype', 'controller', 'devicemodeltype')

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
        fields = ('id', 'url', 'name', 'description', 'tenant')

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
        fields = ('id', 'url', 'name', 'tenant', 'l1interfacetype', 'device')

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
        fields = ('id', 'url', 'tenant', 'l1interfacea', 'l1interfaceb')

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
        fields = ('id', 'url', 'name', 'tenant')

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
        fields = ('id', 'url', 'number', 'name', 'tenant', 'l2interfacetype')   # , 'device'

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
        fields = ('id', 'url', 'name', 'tenant')

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
        fields = ('id', 'url', 'allowedrange', 'tenant', 'l2domaintype', 'l2interface', 'l1interface')

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
        fields = ('id', 'url', 'name', 'tenant')

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
        fields = ('id', 'url', 'name', 'tenant', 'device')

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
        fields = ('id', 'url', 'ipaddress', 'mask', 'tenant', 'device', 'l3interfacetype', 'l2interface', 'l3domain')

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
        fields = ('id', 'url', 'description', 'file', 'tenant', 'uploaded_at')

    def create(self, validated_data):
        uplzip = UploadZip.objects.create(**validated_data)
        task_refresh()
        return uplzip


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Upload
        fields = ('id', 'url', 'description', 'file', 'filename', 'tenant', 'uploaded_at')
