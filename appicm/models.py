from django.contrib.auth.models import User
import django.utils.timezone
from django.db import models
from django.db.models import F, Q
import uuid
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework import authentication
import os
import zipfile
from io import BytesIO
import json
import string
import random
import time
from django.core import management
import logging
import sys
import traceback
from django_google_maps import fields as map_fields
import math
from operator import itemgetter
import ipaddress


plugin_id_remap = ["DeviceModelType", "DeviceType", "CustomMenu", "CustomTemplate", "PluginModule", "IntegrationModule"]
data_migration = {
    "Device": {
        "devicetype": "DeviceType.id",
        "devicemodeltype": "DeviceModelType.id"
    },
    "Controller": {
        "devicetype": "DeviceType.id"
    }
}

# {
#     "IntegrationConfiguration": {
#         "integrationmodule": "IntegrationModule.id",
#         "pm1": "PluginModule.id",
#         "pm2": "PluginModule.id"
#     }
# }


class BearerAuthentication(authentication.TokenAuthentication):
    """
    Simple token based authentication using utvsapitoken.

    Clients should authenticate by passing the token key in the 'Authorization'
    HTTP header, prepended with the string 'Bearer '.  For example:

        Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234
    """
    keyword = 'Bearer'


def set_operation_dirty():
    operations = Operation.objects.all()
    if len(operations) == 0:
        op = Operation.objects.create(reload_tasks=True)
    else:
        operations[0].reload_tasks = True
        operations[0].save()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_stuff(sender, instance=None, created=False, **kwargs):
    if created:
        instance.is_staff = True
        instance.save()

        t = Token.objects.filter(user=instance)
        if len(t) <= 0:
            cur_desc = str(instance.email)
            if cur_desc == "":
                cur_desc = str(instance.username)

            new_tenant = Tenant.objects.create(name=cur_desc)

            cur_profile = AppUser.objects.filter(user=instance)
            if len(cur_profile) <= 0:
                u = AppUser.objects.create(user=instance, hometenant=new_tenant, description=cur_desc)
                u.tenant.add(new_tenant)

            Token.objects.create(user=instance)


def get_key():
    while True:
        test_key = uuid.uuid4().hex[:8]
        recs = Tenant.objects.filter(unique_key=test_key)
        if len(recs) == 0:
            break

    return test_key


class Tenant(models.Model):
    # pkid d4f54cef-c773-4bcb-a91a-42ef071efbb9
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    unique_key = models.CharField(max_length=8, blank=True, default=get_key)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.name


class CLLI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.CharField(max_length=50, default=None, null=True)
    state = models.CharField(max_length=2, default=None, null=True)
    clli = models.CharField(max_length=6, default=None, null=True)
    geolocation = map_fields.GeoLocationField(max_length=100)

    class Meta:
        ordering = ['state', 'city']

    def __str__(self):
        return self.clli


class CustomCLLI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clli = models.CharField(max_length=6, default=None, null=True)

    class Meta:
        ordering = ['clli']

    def __str__(self):
        return self.clli


class LocationType(models.Model):
    description = models.CharField(max_length=30)
    tier = models.IntegerField()
    iconname = models.CharField(max_length=30)
    haslocation = models.BooleanField(default=False)
    hasclli = models.BooleanField(default=False)
    hasclli_addon = models.BooleanField(default=False)
    other_fields = models.CharField(max_length=50, blank=True, default=None, null=True)
    child = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='parent')

    class Meta:
        ordering = ['tier']

    def __str__(self):
        return str(self.description)        # + " :: " + str(self.tier)


class LocationObject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=30)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)
    locationtype = models.ForeignKey(LocationType, on_delete=models.SET_NULL, null=True, blank=True)
    address = map_fields.AddressField(max_length=200, default=None, null=True, blank=True)
    geolocation = map_fields.GeoLocationField(max_length=100, default="", blank=True)
    clli = models.ForeignKey(CLLI, on_delete=models.SET_NULL, null=True, blank=True)
    custom_clli = models.ForeignKey(CustomCLLI, on_delete=models.SET_NULL, null=True, blank=True)
    clli_addon = models.CharField(max_length=10, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return str(self.description)

    def get_clli(self):
        if self.clli:
            return self.clli
        elif self.custom_clli:
            return self.custom_clli

        current_obj = self
        max_loop_count = 5
        loop_count = 0

        while True:
            loop_count += 1
            if loop_count > max_loop_count:
                break

            lhs = LocationHierarchy.objects.filter(object=current_obj)

            if len(lhs) == 0:
                break

            for lh in lhs:
                current_obj = lh.parent
                if lh.parent.get_clli():
                    # clli_addon = str(lh.parent.get_clli()) + str(self.clli_addon)
                    # if clli_addon[-1:] == "-": clli_addon = clli_addon[:-1]
                    return str(lh.parent.get_clli()) + str(self.clli_addon)

    def calculate_distances(self, max_entries=None):
        thisloc = self.geolocation
        if self.geolocation is None or thisloc.lat is None or thisloc.lon is None:
            return []

        cllis = CLLI.objects.all()
        clli_list = []
        for clli in cllis:
            test = math.dist([thisloc.lat, thisloc.lon], [clli.geolocation.lat, clli.geolocation.lon])
            clli_list.append({"distance": test, "clli": {"id": str(clli.id), "city": clli.city, "state": clli.state,
                                                         "clli": clli.clli}})

        shortest_cllis = sorted(clli_list, key=itemgetter('distance'))
        if max_entries:
            return shortest_cllis[:10]

        return shortest_cllis


class LocationHierarchy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object = models.ForeignKey(LocationObject, on_delete=models.SET_NULL, null=True, related_name="locationobject")
    parent = models.ForeignKey(LocationObject, on_delete=models.SET_NULL, null=True, related_name="locationobjectparent")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return str(self.parent) + " :: " + str(self.object)


class CityState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    address = map_fields.AddressField("City, State", max_length=200)
    geolocation = map_fields.GeoLocationField(max_length=100)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)
    clli = models.ForeignKey(CLLI, on_delete=models.SET, null=True, blank=True)

    def __str__(self):
        return str(self.name)

    def calculate_distances(self):
        thisloc = self.geolocation
        cllis = CLLI.objects.all()
        clli_list = []
        for clli in cllis:
            test = math.dist([thisloc.lat, thisloc.lon], [clli.geolocation.lat, clli.geolocation.lon])
            clli_list.append({"distance": test, "clli": {"id": str(clli.id), "city": clli.city, "state": clli.state,
                                                         "clli": clli.clli}})

        shortest_cllis = sorted(clli_list, key=itemgetter('distance'))
        return json.dumps(shortest_cllis)


class Site(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    citystate = models.ForeignKey(CityState, on_delete=models.SET_NULL, null=True, default=None)
    name = models.CharField(max_length=30)
    address = map_fields.AddressField(max_length=200)
    geolocation = map_fields.GeoLocationField(max_length=100)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)
    # clli = models.ForeignKey(CLLI, on_delete=models.SET, null=True, blank=True)

    def __str__(self):
        return self.name

    # def calculate_distances(self):
    #     thisloc = self.geolocation
    #     cllis = CLLI.objects.all()
    #     clli_list = []
    #     for clli in cllis:
    #         test = math.dist([thisloc.lat, thisloc.lon], [clli.geolocation.lat, clli.geolocation.lon])
    #         clli_list.append({"distance": test, "clli": {"id": str(clli.id), "city": clli.city, "state": clli.state,
    #                                                      "clli": clli.clli}})
    #
    #     shortest_cllis = sorted(clli_list, key=itemgetter('distance'))
    #     return json.dumps(shortest_cllis)

# @receiver(post_save, sender=Site)
# def post_save_site(sender, instance=None, created=False, **kwargs):
#     post_save.disconnect(post_save_site, sender=Site)
#     thisloc = instance.geolocation
#     cllis = CLLI.objects.all()
#     shortest = 9999999999
#     clli_list = []
#     for clli in cllis:
#         test = math.dist([thisloc.lat, thisloc.lon], [clli.geolocation.lat, clli.geolocation.lon])
#         # if test < shortest:
#         #     shortest = test
#         clli_list.append({"distance": test, "clli": clli})
#
#     shortest_cllis = sorted(clli_list, key=itemgetter('distance'))
#     print(shortest_cllis)
#     post_save.connect(post_save_site, sender=Site)


class Floor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.name


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, null=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.name


class Row(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.name


class Rack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    height = models.IntegerField()
    row = models.ForeignKey(Row, on_delete=models.CASCADE, null=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.name


def get_default_tenant(obj=False):
    deften = Tenant.objects.filter(name="Default")
    if len(deften) >= 1:
        if obj:
            return deften[0]
        else:
            return deften[0].id
    else:
        deften = Tenant.objects.create(id="00000000-0000-0000-0000-000000000000", name="Default")
        if obj:
            return deften
        else:
            return deften.id


def get_default_authtype(obj=False):
    def_at = AuthType.objects.filter(name="api")
    if len(def_at) >= 1:
        if obj:
            return def_at[0]
        else:
            return def_at[0].id
    else:
        deften = AuthType.objects.create(id="00000000-0000-0000-0000-000000000000", name="api")
        if obj:
            return deften
        else:
            return deften.id


class TaskResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, null=True)
    taskname = models.CharField(max_length=30)
    runtime = models.DateTimeField(auto_now_add=True)
    result = models.TextField(null=True)

    class Meta:
        ordering = ['-runtime']

    def __str__(self):
        return str(self.runtime) + " -- " + str(self.taskname)


def get_file_path(instance, filename):
    ext = "." + filename.split('.')[-1]
    filename = string_generator(8) + ext
    # fix for django.core.exceptions.SuspiciousFileOperation: Detected path traversal attempt
    # fp = os.path.join('upload', filename)
    # fp = os.path.join(settings.BASE_DIR, fp)
    fp = os.path.join("upload", filename)
    # print(fp)
    return fp


class UploadZip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=255, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=True, null=True, default=None)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    file = models.FileField(upload_to=get_file_path)
    pkg_ver = models.FloatField(blank=True, default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.tenant:
            return self.description + " (" + self.tenant.name + ")"
        else:
            return self.description

    def filename(self):
        fpath = str(self.file)
        flist = fpath.split(os.path.sep)
        if len(flist) > 0:
            return flist[-1]
        else:
            return str(self.file)

    def base_desc(self):
        fl = self.description.split("-")
        if len(fl) > 0:
            return fl[0]


def string_generator(size):
    t = int(time.time() * 1000.0)
    random.seed(((t & 0xff000000) >> 24) +
                ((t & 0x00ff0000) >> 8) +
                ((t & 0x0000ff00) << 8) +
                ((t & 0x000000ff) << 24))

    chars = string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for _ in range(size))


def delete_remap_database_fields(uploadzip_instance, default_tenant):
    # when a module is deleted for a tenant, we need to clear plugin_id from all records associated with the plugin.
    # also, when a module exists for both the global tenant and a given individual tenant, when the individual tenant
    #  module is deleted, we need to migrate any relevant attributes to the global tenant

    log = ""
    plugin_id = uploadzip_instance.plugin_id
    if plugin_id:
        for cl in plugin_id_remap:
            log += "unmapping fields in " + str(cl) + "...\n"
            # del_str = cl + ".objects.filter(plugin_id=\"" + plugin_id + "\").delete()"
            # eval(del_str)
            upd_str = cl + ".objects.filter(plugin_id=\"" + str(plugin_id) + "\").update(plugin_id=None)"
            eval(upd_str)
    else:
        log += "No plugin_id. This shouldn't happen.\n"

    # if uploadzip_instance.tenant != default_tenant:
    if True:
        # this must be a module deleted from an individual tenant; do we need to migrate to global plugin?
        uz_test = UploadZip.objects.filter(tenant=uploadzip_instance.tenant).filter(description=uploadzip_instance.description)
        if len(uz_test) > 0:
            log += "module exists in local tenant; data migration required\n"
            for table in data_migration:
                table_mappings = data_migration[table]
                log += "migrating data in " + str(table) + "\n"
                get_str = table + ".objects.filter(tenant_id=\"" + str(uploadzip_instance.tenant.id) + "\")"
                migrate_records = eval(get_str)
                for record in migrate_records:
                    for field_migration in table_mappings:
                        dest_mapping = table_mappings[field_migration]
                        dest_mapping_list = dest_mapping.split(".")
                        # current_name = eval(str(table) + "." + str(field_migration) + ".name")
                        current_name = uploadzip_instance.description
                        current_records_str = dest_mapping_list[0] + ".objects.filter(tenant_id=\"" + str(uploadzip_instance.tenant.id) + "\").filter(plugin_id=\"" + str(uploadzip_instance.plugin_id) + "\").filter(name=\"" + str(current_name) + "\")"
                        current_records = eval(current_records_str)

                        if len(current_records) > 0:
                            log += "more than one record... shouldn't really happen\n"
                            log += str(current_records) + "\n"
                            current_record = current_records[0]
                        elif len(current_records) == 1:
                            current_record = current_records[0]
                        else:
                            current_record = None

                        if current_record:
                            upd_str = table + ".objects.filter(id=\"" + str(record.id) + "\").update(\"" + str(field_migration + "\"=\"" + str(current_record.id) + "\"")
                            print(upd_str)
                            eval(upd_str)
                            log += str(upd_str) + "\n"
        else:
            log += "remapping not running;" + str(uz_test) + "::" + str(uploadzip_instance.tenant) + "::" + str(uploadzip_instance.description) + "\n"

    return log


def insert_remap_database_fields(uploadzip_instance, default_tenant):
    # when a module is uploaded for a tenant, look to see if there are any db records that have been cleared
    #  by a previous module uninstall. If so, we need to migrate those to the new module and de-duplicate
    # also, when a module exists for the global tenant, if a module is uploaded for a given individual tenant,
    #  migrate any relevant attributes to their local tenant

    log = ""
    current_name = uploadzip_instance.description
    for table in plugin_id_remap:
        log += "* Remapping fields in " + str(table) + "...\n"
        get_str = table + ".objects.filter(tenant_id=\"" + str(uploadzip_instance.tenant.id) + "\").filter(plugin_id=\"" + str(uploadzip_instance.plugin_id) + "\")"
        mapped_records = eval(get_str)
        get_str = table + ".objects.filter(plugin_id=None).filter(plugin_name=\"" + str(current_name) + "\")"
        unmapped_records = eval(get_str)

        mapped_names = {}
        log += "..mapped_records:\n"
        for record in mapped_records:
            log += "...." + str(record.name) + "\n"
            mapped_names[str(record.name)] = record

        log += "..unmapped_records:\n"
        for record in unmapped_records:
            log += "...." + str(record.name)
            if record.name in mapped_names:
                log += " [updating]\n"
                record.plugin_id = mapped_names[str(record.name)].plugin_id
                record.plugin_name = mapped_names[str(record.name)].description
                record.save()
                # try:
                del mapped_names[str(record.name)]
                # except Exception as e:
                #     log += "....Exception deleting mapped record" + str(e) + "\n"
            else:
                log += " [remapping]\n"
                record.plugin_id = uploadzip_instance.plugin_id
                # record.plugin_name = uploadzip_instance.description
                # record.tenant = uploadzip_instance.tenant
                record.save()

    # if uploadzip_instance.tenant != default_tenant:
    if True:
        # this must be a module uploaded in an individual tenant; do we need to migrate from global plugin?
        #  yes, but only if the module no longer exists in the individual tenant
        uz_test = UploadZip.objects.filter(tenant=default_tenant).filter(description=uploadzip_instance.description)
        if len(uz_test) > 0:
            log += "module exists in global tenant; data migration required\n"
            for table in data_migration:
                table_mappings = data_migration[table]
                log += "* Migrating data in " + str(table) + "\n"
                if uploadzip_instance.tenant == default_tenant and table == "Controller":
                    # if uploading to the global tenant, check for abandoned records in individual tenants
                    get_str = table + ".objects.filter(Q(devicetype__plugin_id__isnull=True) | Q(devicetype__plugin_id=\"\")).filter(devicetype__name=\"" + str(uploadzip_instance.description) + "\")"
                else:
                    get_str = table + ".objects.filter(tenant_id=\"" + str(uploadzip_instance.tenant.id) + "\")"
                migrate_records = eval(get_str)
                # print(get_str, migrate_records)
                log += "..records to migrate " + str(migrate_records) + "\n"
                for record in migrate_records:
                    for field_migration in table_mappings:
                        dest_mapping = table_mappings[field_migration]
                        dest_mapping_list = dest_mapping.split(".")
                        # current_name_str = str(table) + "." + str(field_migration) + ".name"
                        # print(current_name_str)
                        # current_name = eval(current_name_str)
                        current_name = uploadzip_instance.description
                        current_records_str = dest_mapping_list[0] + ".objects.filter(tenant_id=\"" + str(uploadzip_instance.tenant.id) + "\").filter(plugin_id=\"" + str(uploadzip_instance.plugin_id) + "\").filter(name=\"" + str(current_name) + "\")"
                        current_records = eval(current_records_str)

                        if len(current_records) > 0:
                            log += "more than one record... shouldn't really happen\n"
                            log += str(current_records) + "\n"
                            current_record = current_records[0]
                        elif len(current_records) == 1:
                            current_record = current_records[0]
                        else:
                            current_record = None

                        if current_record:
                            upd_str = table + ".objects.filter(id=\"" + str(record.id) + "\").update(" + str(field_migration + "=\"" + str(current_record.id) + "\")")
                            print(upd_str)
                            eval(upd_str)
                            log += str(upd_str) + "\n"

    return log


def write_file(out_filename, content):
    with open(os.path.join("packages", out_filename), 'w') as out_file:
        out_file.write(content)


def read_file(in_filename, default_content):
    try:
        with open(os.path.join("packages", in_filename), 'r+') as in_file:
            read_val = in_file.read()
            if read_val == "" or read_val is None:
                return default_content
            else:
                return read_val
    except:
        return default_content


@receiver(post_save, sender=UploadZip)
def post_save_uploadzip(sender, instance=None, created=False, **kwargs):
    logdata = ""
    default_tenant = get_default_tenant(obj=True)
    post_save.disconnect(post_save_uploadzip, sender=UploadZip)
    try:
        unzipped = zipfile.ZipFile(BytesIO(instance.file.read()))
        pkg = unzipped.read("package.json")
        pkg_json = json.loads(pkg.decode("utf-8"))
        desc = str(pkg_json.get("name", str(instance.file.name)))
        logdata += "description=" + str(desc) + "\n"
        # logging.error("description=" + str(desc))
        instance.description = desc
        pkg_ver = float(pkg_json.get("version", 0.0))

        # construct uuid for this paticular tenant/plugin combination
        base_uuid = pkg_json.get("unique_id")
        uuid_list = base_uuid.split("-")
        uuid_list[0] = instance.tenant.unique_key
        table_map = json.loads(read_file('table_map.json', json.dumps({"current_index": 1})))

        logdata += "version=" + str(pkg_ver) + "\n"
        # logging.error("version=" + str(pkg_ver))
        instance.pkg_ver = pkg_ver
        if not instance.tenant:
            instance.tenant = default_tenant
        logdata += "tenant=" + str(instance.tenant) + "\n"
        # logging.error("tenant=" + str(instance.tenant))
        # Ensure that the plugin_id is unique
        uzs = UploadZip.objects.filter(tenant=instance.tenant).filter(description=desc)
        if len(uzs) == 0:
            plugin_id = None
            while True:
                plugin_id = string_generator(20)
                pz = UploadZip.objects.filter(plugin_id=plugin_id)
                if len(pz) == 0:
                    break
            instance.plugin_id = plugin_id
            instance.save()
            for p in pkg_json.get("files", []):
                logdata += "processing entry=" + str(p) + "\n"
                # logging.error("processing entry=" + str(p))
                p_target = p.get("target", "")
                p_file = p.get("file", "")
                logdata += "target=" + str(p_target) + "\n"
                # logging.error("target=" + str(p_target))
                logdata += "file=" + str(p_file) + "\n"
                # logging.error("file=" + str(p_file))
                fp = "upload"
                ext = ".json"
                if p_target == "scripts":
                    fp = "scripts"
                    ext = ".py"
                elif p_target == "template":
                    fp = os.path.join("templates", "custom")
                    ext = ".html"

                fp = os.path.join(settings.BASE_DIR, fp)
                fn = fp + "/f" + string_generator(8) + ext
                logdata += "new filename=" + str(fn) + "\n"
                # logging.error("new filename=" + str(fn))
                if p_target == "database":
                    lines = '"fields": {\n\t\t"tenant": "' + str(instance.tenant.id) + '",\n\t\t"plugin_name": "' + desc + '",\n\t\t"plugin_id": "' + plugin_id + '",'
                    bfd = unzipped.read(p_file).decode("utf-8").replace('"fields": {', lines)

                    # generate id for fields in model
                    table_record_id = {}
                    bfd_json = json.loads(bfd)
                    for r in bfd_json:
                        db_table = r.get('model')
                        if db_table not in table_record_id:
                            table_record_id[db_table] = 1

                        if db_table in table_map:
                            table_id = table_map[db_table]
                        else:
                            idx = table_map["current_index"]
                            table_map["current_index"] = idx + 1
                            table_id = "{:04x}".format(idx)
                            table_map[db_table] = table_id
                            write_file('table_map.json', json.dumps(table_map))

                        uuid_list[1] = table_id
                        uuid_list[2] = "{:04x}".format(table_record_id[db_table])
                        table_record_id[db_table] += 1

                        r["fields"]["id"] = "-".join(uuid_list)
                    open(fn, 'wb').write(json.dumps(bfd_json).encode("utf-8"))
                    # open(fn, 'wb').write(bfd.encode("utf-8"))
                else:
                    open(fn, 'wb').write(unzipped.read(p_file))

                try:
                    i = Upload.objects.create(description=p_file, type=p_target, file=fn, uploadzip=instance,
                                              tenant=instance.tenant, plugin_id=plugin_id)
                    i.save()
                    logdata += "upload object=" + str(i) + "\n"
                    # logging.error("upload object=" + str(i))
                except Exception as e:
                    logdata += "exception uploading object=" + str(e) + "\n"
                    # logging.error("exception uploading object=" + str(e))

                if p_target == "database":
                    # before we import the database, check for any database field remapping that needs to happen
                    logdata += str(insert_remap_database_fields(instance, default_tenant))

                    management.call_command('loaddata', fn)
                    rels = p.get("relationships", [])
                    for rel in rels:
                        logdata += "processing relationship update=" + str(rel) + "\n"
                        rel_st = rel.get("source_table")
                        rel_sfm = rel.get("source_field_match")
                        rel_sfl = rel.get("source_field_link")
                        rel_dt = rel.get("destination_table")
                        rel_dfm = rel.get("destination_field_match")
                        rel_dfl = rel.get("destination_field_link")
                        if rel_st and rel_sfm and rel_sfl and rel_dt and rel_dfm and rel_dfl:
                            # src_objs = eval(rel_st).objects.filter(plugin_id=plugin_id).filter(eval(rel_sfm))
                            # dst_objs = eval(rel_dt).objects.filter(plugin_id=plugin_id).filter(eval(rel_dfm))
                            src_str = rel_st + ".objects.filter(plugin_id=\"" + plugin_id + "\").filter(" + rel_sfm + ")"
                            dst_str = rel_dt + ".objects.filter(plugin_id=\"" + plugin_id + "\").filter(" + rel_dfm + ")"
                            src_objs = eval(src_str)
                            dst_objs = eval(dst_str)
                            logdata += "# source objects=" + str(src_str) + "::" + str(len(src_objs)) + "\n"
                            logdata += "# dest objects=" + str(dst_str) + "::" + str(len(dst_objs)) + "\n"

                            if len(src_objs) == 1 and len(dst_objs) == 1:
                                src_obj = src_objs[0]
                                dst_obj = dst_objs[0]
                                src_val = eval("src_obj." + rel_sfl)
                                logdata += "..srcid=" + str(src_obj.id) + "\n"
                                logdata += "..dstid=" + str(dst_obj.id) + "\n"
                                # lnk_str = "dst_obj." + rel_dfl + " = src_val"
                                # print(lnk_str)
                                # eval(lnk_str)
                                # dst_obj.devicetype__id = src_val
                                # dst_obj.save()
                                dst_lnk = rel_dt + ".objects.filter(id=\"" + str(dst_obj.id) + "\").update(" + rel_dfl + "=\"" + str(src_val) + "\")"
                                logdata += ".." + str(dst_lnk) + "\n"
                                # print(dst_lnk)
                                eval(dst_lnk)

                    # logdata += str(insert_remap_database_fields(instance, default_tenant))

                # call_command('makemigrations')
                # call_command('migrate')

                # for libitem in unzipped.namelist():
                #     if libitem.startswith('')
                #     if libitem.startswith('__MACOSX/'):
                #         continue
                #     fn = "upload/" + libitem
                #     open(fn, 'wb').write(unzipped.read(libitem))
                #     i = Upload.objects.create(description=instance.description + "-" + fn, file=fn)
                #     i.save()

            set_operation_dirty()
            TaskResult.objects.create(tenant=instance.tenant, taskname="Package Upload", result=logdata)
            post_save.connect(post_save_uploadzip, sender=UploadZip)
        else:
            logdata += "Module already exists for this tenant; aborting"
            TaskResult.objects.create(tenant=instance.tenant, taskname="Package Upload", result=logdata)
            instance.delete()
            instance = None
            post_save.connect(post_save_uploadzip, sender=UploadZip)
            raise FileExistsError("Error: this module already exists for this tenant.")
    except Exception as e:
        logging.error("exception on upload")
        logging.error(e)
        traceback.print_exc(file=sys.stdout)
        post_save.connect(post_save_uploadzip, sender=UploadZip)


@receiver(models.signals.pre_delete, sender=UploadZip)
def auto_delete_uploadzip_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `UploadZip` object is deleted.
    """
    log = delete_remap_database_fields(instance, get_default_tenant(obj=True))
    TaskResult.objects.create(tenant=instance.tenant, taskname="Package Delete", result=log)

    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        except Exception as e:
            print(e)
            TaskResult.objects.create(tenant=instance.tenant, taskname="Package Delete", result=e)
    else:
        TaskResult.objects.create(tenant=instance.tenant, taskname="Package Delete", result="Error; instance doesn't have a file.")

    set_operation_dirty()


@receiver(models.signals.pre_save, sender=UploadZip)
def auto_delete_uploadzip_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem
    when corresponding `UploadZip` object is updated
    with new file.
    """
    # This isn't really supported...
    if not instance.pk:
        return False

    try:
        old_file = UploadZip.objects.get(pk=instance.pk).file
    except UploadZip.DoesNotExist:
        return False

    new_file = instance.file
    if not old_file == new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


class Upload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=255, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=True, null=True, default=None)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    file = models.FileField(upload_to='upload')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=10, blank=True, null=True, default=None)
    uploadzip = models.ForeignKey(UploadZip, on_delete=models.CASCADE, null=True, default=None)

    def __str__(self):
        return self.description + " (" + self.tenant.name + ")"

    def filedata(self):
        try:
            try:
                return self.file.read().decode("utf-8")
            except Exception:
                return self.file.read()
        except Exception:
            return self.file

    def fspath(self):
        return self.file.name
        # return os.path.join(os.path.dirname(os.path.realpath(__file__)), self.file.name)

    def filename(self):
        fpath = str(self.file)
        flist = fpath.split(os.path.sep)
        if len(flist) > 0:
            return flist[-1]
        else:
            return str(self.file)

    def base_desc(self):
        fl = self.description.split("-")
        if len(fl) > 0:
            return fl[0]


@receiver(models.signals.post_delete, sender=Upload)
def auto_delete_upload_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `Upload` object is deleted.
    """
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        except Exception as e:
            print(e)


@receiver(models.signals.pre_save, sender=Upload)
def auto_delete_upload_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem
    when corresponding `Upload` object is updated
    with new file.
    """
    if not instance.pk:
        return False

    try:
        old_file = Upload.objects.get(pk=instance.pk).file
    except Upload.DoesNotExist:
        return False

    new_file = instance.file
    if not old_file == new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


class AppUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=30, null=False, blank=True, default=None)
    hometenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, default=None, related_name='hometenant')
    tenant = models.ManyToManyField(Tenant, blank=True)
    localtz = models.CharField(max_length=30, null=False, blank=True, default="Etc/GMT")

    def __str__(self):
        return self.user.get_username()


@receiver(pre_delete, sender=AppUser)
def pre_delete_user(sender, instance=None, created=False, **kwargs):
    pre_delete.disconnect(pre_delete_user, sender=AppUser)
    User.objects.all().filter(id=instance.user.id).delete()
    pre_delete.connect(pre_delete_user, sender=AppUser)


class AuthType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class DeviceModelType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plugin_id = models.CharField(max_length=20, default=None, null=True, blank=True)
    plugin_name = models.CharField(max_length=20, default=None, null=True, blank=True)
    name = models.CharField(max_length=50)
    named_id = models.CharField(max_length=100, null=True, blank=True, default=None)
    device_type = models.CharField(max_length=50, null=True, blank=True, default=None)
    size_rack_u = models.FloatField(null=True, blank=True, default=0)
    portcount = models.IntegerField(null=True, blank=True, default=None)
    portlist = models.TextField(blank=True, null=True, default=None)

    class Meta:
        ordering = ['tenant', 'name']

    def __str__(self):
        return self.name + " (" + self.tenant.name + ")"


class DeviceType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    plugin_name = models.CharField(max_length=20, default=None, null=True)
    name = models.CharField(max_length=30)
    # py_mod_name = models.CharField(max_length=30)
    authtype = models.ForeignKey(AuthType, on_delete=models.CASCADE, default=get_default_authtype)
    defaultmgmtaddress = models.CharField(max_length=100, default="", null=True, blank=True)
    supportscontroller = models.BooleanField("Is Controller / Management System?", default=False)
    parmdef = models.JSONField(default=dict)

    def __str__(self):
        return self.name + " (" + self.tenant.name + ")"


class Controller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    devicetype = models.ForeignKey(DeviceType, on_delete=models.CASCADE)
    authparm = models.JSONField(default=dict)
    mgmtaddress = models.CharField(max_length=100, default="", null=True, blank=True)
    rawdata = models.JSONField(blank=True, default=dict, null=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name + " (" + str(self.devicetype) + ")"


class Device(models.Model):
    class DeviceStatus(models.IntegerChoices):
        UNKNOWN = 0, 'Unknown'
        OFFLINE = 1, 'Offline'
        DORMANT = 2, 'Dormant'
        ALERTING = 3, 'Alerting'
        ONLINE = 4, 'Online'
        NOTINSTALLED = 5, 'Not Installed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    basemac = models.CharField(max_length=30, default=None, null=True, blank=True)
    devicetype = models.ForeignKey(DeviceType, on_delete=models.CASCADE)
    serial_number = models.CharField(max_length=30, default="", null=True, blank=True)
    authparm = models.JSONField(default=dict, blank=True)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, default=None, null=True, blank=True)
    orphaned = models.BooleanField(default=False)
    mgmtaddress = models.CharField(max_length=100, default="", null=True, blank=True)
    devicemodeltype = models.ForeignKey(DeviceModelType, on_delete=models.CASCADE, default="4b64171e-63b9-43bb-ac17-47a3784c8167")
    rawconfig = models.JSONField(default=dict, editable=False)
    current_version = models.CharField(max_length=50, blank=True, default=None, null=True)
    other_data = models.JSONField(blank=True, null=False, default=dict)
    status = models.IntegerField(default=DeviceStatus.UNKNOWN, choices=DeviceStatus.choices)

    def __str__(self):
        return str(self.name) + " -- " + str(self.serial_number) + " (" + str(self.devicemodeltype) + ")"


    def get_status(self):
        return self.DeviceStatus.choices[self.status][1]


class L1InterfaceType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=500, default="")

    def __str__(self):
        return self.name + " (" + self.description + ")"


class L1Interface(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    l1interfacetype = models.ForeignKey(L1InterfaceType, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=50, default=None, null=True, blank=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    rawdata = models.JSONField(editable=False, default=dict)

    class Meta:
        ordering = ['tenant', 'device', 'name']

    def __str__(self):
        if self.description:
            return str(self.device) + ", Port " + str(self.name) + " [" + self.description + "]"
        else:
            return str(self.device) + ", Port " + str(self.name)


class L1Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    l1interfacea = models.ForeignKey(L1Interface, on_delete=models.CASCADE, related_name='l1interfacea')
    l1interfaceb = models.ForeignKey(L1Interface, on_delete=models.CASCADE, related_name='l1interfaceb')


class L2InterfaceType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class L2Interface(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    l2interfacetype = models.ForeignKey(L2InterfaceType, on_delete=models.CASCADE)
    number = models.IntegerField(default=0)
    name = models.CharField(max_length=30)
    # device = models.ForeignKey(Device, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class L2DomainType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class L2Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    l2domaintype = models.ForeignKey(L2DomainType, on_delete=models.CASCADE)
    l2interface = models.ForeignKey(L2Interface, on_delete=models.CASCADE)
    l1interface = models.ForeignKey(L1Interface, on_delete=models.CASCADE)
    allowedrange = models.CharField(max_length=30)

    class Meta:
        ordering = ['tenant', 'l1interface__device', 'l1interface']

    def __str__(self):
        if self.l2domaintype.name == "Access":
            return str(self.l1interface) + " (" + str(self.l2domaintype) + ", VLAN " + str(self.l2interface.number) + ")"
        else:
            return str(self.l1interface) + " (" + str(self.l2domaintype) + ", " + str(self.allowedrange) + ")"


class L3InterfaceType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class L3Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    device = models.ManyToManyField(Device, blank=True)

    def __str__(self):
        return self.name


class L3Interface(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    l3interfacetype = models.ForeignKey(L3InterfaceType, on_delete=models.CASCADE)
    l2interface = models.ForeignKey(L2Interface, on_delete=models.CASCADE, blank=True, default=None, null=True)
    l3domain = models.ForeignKey(L3Domain, on_delete=models.CASCADE)
    ipaddress = models.CharField(max_length=30)
    mask = models.CharField(max_length=30)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)

    def __str__(self):
        return self.ipaddress + " " + self.mask


class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    nameornumber = models.CharField(max_length=30)
    devicemodeltype = models.ForeignKey(DeviceModelType, on_delete=models.CASCADE)

    class Meta:
        ordering = ['device', 'nameornumber']

    def __str__(self):
        return str(self.device) + " -- " + str(self.nameornumber) + " (" + str(self.devicemodeltype) + ")"


class SubModule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    nameornumber = models.CharField(max_length=30)
    devicemodeltype = models.ForeignKey(DeviceModelType, on_delete=models.CASCADE)

    class Meta:
        ordering = ['module__device', 'module__nameornumber', 'nameornumber']

    def __str__(self):
        return str(self.module.device) + " -- " + str(self.module.nameornumber) + "/" + str(self.nameornumber) + " (" + str(self.devicemodeltype) + ")"


class ManagementInterface(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, default=None, blank=True, null=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, default=None, blank=True, null=True)
    devicetype = models.ForeignKey(DeviceType, on_delete=models.CASCADE)
    ipaddress = models.CharField(max_length=30, default=None, blank=True, null=True)
    username = models.CharField(max_length=30, default=None, blank=True, null=True)
    password = models.CharField(max_length=30, default=None, blank=True, null=True)

    class Meta:
        ordering = ['module__device', 'module__nameornumber']

    def __str__(self):
        if self.device:
            return str(self.device) + " -- " + str(self.ipaddress) + " (" + str(self.devicetype) + ")"
        else:
            return str(self.module) + " -- " + str(self.ipaddress) + " (" + str(self.devicetype) + ")"


class PDUOutlet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    portid = models.CharField(max_length=30, default=None, blank=True, null=True)

    class Meta:
        ordering = ['device', 'portid']

    def __str__(self):
        return str(self.device) + " (" + str(self.portid) + ")"


class TerminalLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    vtyid = models.CharField(max_length=30, default=None, blank=True, null=True)
    lineid = models.CharField(max_length=30, default=None, blank=True, null=True)

    class Meta:
        ordering = ['device', 'lineid']

    def __str__(self):
        return str(self.device) + " (" + str(self.lineid) + ")"


class ElementConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, default=None, blank=True, null=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, default=None, blank=True, null=True)
    pduoutlet = models.ManyToManyField(PDUOutlet, blank=True)
    terminalline = models.ManyToManyField(TerminalLine, blank=True)

    class Meta:
        ordering = ['device', 'module__device', 'module__nameornumber']

    def __str__(self):
        if self.device:
            return str(self.device)
        else:
            return str(self.module)


class HomeLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=None, null=True)
    name = models.CharField(max_length=50)
    url = models.CharField(max_length=200)
    icon_url = models.CharField(max_length=200)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class PluginModule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    plugin_name = models.CharField(max_length=20, default=None, null=True)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=50, null=True, default=None)
    entity_name = models.CharField(max_length=30, null=True, default=None)
    entity_name_plural = models.CharField(max_length=30, null=True, default=None)
    # py_mod_name = models.CharField(max_length=30, null=True, default=None)
    sync_interval = models.IntegerField(null=True, blank=True, default=60)
    devicetype = models.ForeignKey(DeviceType, on_delete=models.SET_NULL, null=True, default=None)
    default_icon = models.CharField(max_length=250, null=True, default=None)

    def __str__(self):
        return self.name + " (" + self.tenant.name + ")"


class Tunnel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    tunnelId = models.CharField(max_length=50, default=None, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    rawdata = models.JSONField(editable=False, default=dict, null=True, blank=True)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, blank=False, null=True)

    def __str__(self):
        return str(self.name)


class IntegrationModule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    plugin_name = models.CharField(max_length=20, default=None, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    description = models.CharField(max_length=50, null=True, default=None)
    notes = models.TextField(null=True, blank=True, default=None)
    pm1 = models.ForeignKey(PluginModule, related_name="pm1", on_delete=models.SET_NULL, null=True)
    pm2 = models.ForeignKey(PluginModule, related_name="pm2", on_delete=models.SET_NULL, null=True)
    # py_mod_name = models.CharField(max_length=30, default=None, null=True)
    sync_interval = models.IntegerField(null=True, blank=True, default=60)
    is_multi_select = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)


class IntegrationConfiguration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    integrationmodule = models.ForeignKey(IntegrationModule, on_delete=models.SET_NULL, null=True)
    pm1 = models.ManyToManyField(Controller, related_name="pm1")
    pm2 = models.ManyToManyField(Controller, related_name="pm2")

    def __str__(self):
        if self.integrationmodule:
            return str(self.integrationmodule.name)
        else:
            return str(self.id)


class Operation(models.Model):
    reload_tasks = models.BooleanField(default=False)

    def __str__(self):
        return str(self.reload_tasks)


class CloudImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    controller = models.ForeignKey(Controller, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    description = models.CharField(max_length=100, blank=True, null=True, default=None)
    default_username = models.CharField(max_length=100, blank=True, null=True, default=None)
    cloudid = models.CharField(max_length=100, blank=True, null=True, default=None)
    rawdata = models.JSONField(blank=True, null=True, default=dict)
    skip_sync = models.BooleanField(default=False, editable=False)
    last_update = models.DateTimeField(default=django.utils.timezone.now)
    last_sync = models.DateTimeField(null=True, default=None, blank=True)
    last_sync_log = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        if self.description:
            return self.cloudid + " (" + self.description + ")"
        else:
            return self.cloudid


class CloudVPC(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    controller = models.ForeignKey(Controller, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    cidr = models.CharField(max_length=20, blank=True, null=True, default=None)
    description = models.CharField(max_length=100, blank=True, null=True, default=None)
    cloudid = models.CharField(max_length=100, blank=True, null=True, default=None)
    rawdata = models.JSONField(blank=True, null=True, default=dict)
    skip_sync = models.BooleanField(default=False, editable=False)
    last_update = models.DateTimeField(default=django.utils.timezone.now)
    last_sync = models.DateTimeField(null=True, default=None, blank=True)
    last_sync_log = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        if self.cloudid:
            return self.cloudid + " (" + self.cidr + " || " + self.description + ")"
        else:
            return "(" + self.cidr + " || " + self.description + ")"


class CloudSubnet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    controller = models.ForeignKey(Controller, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    vpc = models.ForeignKey(CloudVPC, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    cidr = models.CharField(max_length=20, blank=True, null=True, default=None)
    description = models.CharField(max_length=100, blank=True, null=True, default=None)
    cloudid = models.CharField(max_length=100, blank=True, null=True, default=None)
    rawdata = models.JSONField(blank=True, null=True, default=dict)
    assign_public_ip = models.BooleanField(default=True, editable=True)
    skip_sync = models.BooleanField(default=False, editable=False)
    last_update = models.DateTimeField(default=django.utils.timezone.now)
    last_sync = models.DateTimeField(null=True, default=None, blank=True)
    last_sync_log = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        if self.cloudid:
            return self.vpc.cloudid + "/" + self.cloudid + " (" + self.cidr + " || " + self.description + ")"
        else:
            return self.vpc.cloudid + " (" + self.cidr + " || " + self.description + ")"


def aws_sg_parser(rulelist):
    out = ""
    for r in rulelist:
        if r["IpProtocol"] == "-1":
            prefix = "permit ip"
        else:
            prefix = "permit " + r["IpProtocol"]

        if "FromPort" in r:
            if r["FromPort"] == r["ToPort"]:
                portseq = " eq " + str(r["FromPort"])
            else:
                portseq = " range " + str(r["FromPort"]) + " " + str(r["ToPort"])
        else:
            portseq = " any"

        for v4 in r["IpRanges"]:
            desc = ""
            if "Description" in v4:
                desc = " remark " + v4["Description"]
            out += prefix + " " + v4["CidrIp"] + portseq + desc + "\n"
        for v6 in r["Ipv6Ranges"]:
            desc = ""
            if "Description" in v6:
                desc = " remark " + v6["Description"]
            out += prefix + " " + v6["CidrIpv6"] + portseq + desc + "\n"
        for g in r["UserIdGroupPairs"]:
            desc = ""
            if "Description" in g:
                desc = " remark " + g["Description"]
            out += prefix + " " + g["GroupId"] + portseq + desc + "\n"

    return out


class CloudSecurityGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    controller = models.ForeignKey(Controller, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    description = models.CharField(max_length=100, blank=True, null=True, default=None)
    cloudvpc = models.ForeignKey(CloudVPC, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    cloudid = models.CharField(max_length=100, blank=True, null=True, default=None)
    rawdata = models.JSONField(blank=True, null=True, default=dict)
    skip_sync = models.BooleanField(default=False, editable=False)
    last_update = models.DateTimeField(default=django.utils.timezone.now)
    last_sync = models.DateTimeField(null=True, default=None, blank=True)
    last_sync_log = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return self.cloudid + " (" + self.description + ")"

    def inboundrules(self):
        rules = json.loads(self.rawdata.replace("'", '"'))["IpPermissions"]
        return aws_sg_parser(rules)

    def outboundrules(self):
        rules = json.loads(self.rawdata.replace("'", '"'))["IpPermissionsEgress"]
        return aws_sg_parser(rules)


class CloudInstance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    controller = models.ForeignKey(Controller, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    cloudimage = models.ForeignKey(CloudImage, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    # instanceautomation = models.ForeignKey(InstanceAutomation, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    automationvars = models.TextField(blank=True, null=True, default=None)
    cloudsubnet = models.ForeignKey(CloudSubnet, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    cloudsecuritygroup = models.ManyToManyField(CloudSecurityGroup, blank=True)
    srcdstcheck = models.BooleanField(default=True, editable=True)
    username = models.CharField(max_length=100, blank=True, null=True, default=None)
    description = models.CharField(max_length=100, blank=True, null=True, default=None)
    publicip = models.CharField(max_length=100, blank=True, null=True, default=None)
    publicdns = models.CharField(max_length=100, blank=True, null=True, default=None)
    privateip = models.CharField(max_length=100, blank=True, null=True, default=None)
    cloudid = models.CharField(max_length=100, blank=True, null=True, default=None)
    imagesize = models.CharField(max_length=100, blank=True, null=True, default=None)
    userdata = models.TextField(blank=True, null=True, default=None)
    prevuserdata = models.TextField(blank=True, null=True, default=None, editable=False)
    rawdata = models.JSONField(blank=True, null=True, default=dict)
    force_script = models.BooleanField("Force Instance Script Update", default=False, editable=True)
    skip_sync = models.BooleanField(default=False, editable=False)
    last_update = models.DateTimeField(default=django.utils.timezone.now)
    last_sync = models.DateTimeField(null=True, default=None, blank=True)
    last_sync_log = models.TextField(blank=True, null=True, default=None)
    last_deployed_hash = models.CharField(max_length=32, blank=True, null=True, default=None)

    def __str__(self):
        if self.cloudid:
            return self.cloudid + " (" + self.description + ")"
        else:
            return self.description
    #
    # def instanceautomationscript(self):
    #     return fix_up_command(self.instanceautomation.rawdata)
    #
    # def instanceautomationscripthash(self):
    #     if self.instanceautomationscript() is None or self.instanceautomationscript() == "":
    #         return ""
    #     else:
    #         return hashlib.md5(self.instanceautomationscript().encode("utf-8")).hexdigest()


class CustomMenu(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    plugin_name = models.CharField(max_length=20, default=None, null=True)
    name = models.CharField(max_length=20, blank=False)
    icon = models.CharField(max_length=20, blank=True, default="icon-3d-object_20")

    def __str__(self):
        return self.name


class CustomTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    plugin_id = models.CharField(max_length=20, default=None, null=True)
    plugin_name = models.CharField(max_length=20, default=None, null=True)
    custommenu = models.ForeignKey(CustomMenu, on_delete=models.SET_NULL, null=True, blank=False, default=None)
    name = models.CharField(max_length=20, blank=False)
    pluginmodule = models.ForeignKey(PluginModule, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    integrationmodule = models.ForeignKey(IntegrationModule, on_delete=models.SET_NULL, null=True, blank=True, default=None)

    def __str__(self):
        return self.custommenu.name + "--" + self.name


class Construct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    constructId = models.CharField(max_length=50, default=None, null=True)
    type = models.CharField(max_length=50, default=None, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    rawdata = models.JSONField(editable=False, default=dict)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, blank=True, null=True)
    integrationconfiguration = models.ForeignKey(IntegrationConfiguration, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return self.type + ":" + self.name


# class TunnelPort(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     portnumber = models.IntegerField(default=0)
#
#     class Meta:
#         ordering = ['portnumber', ]
#
#     def __str__(self):
#         return str(self.portnumber)
#
#
# class TunnelClient(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
#     tunnelport = models.ForeignKey(TunnelPort, on_delete=models.SET_NULL, blank=True, null=True)
#     description = models.CharField(max_length=50, default=None, null=True)
#     pid = models.IntegerField(default=0, blank=True)
#     log = models.TextField(null=True, blank=True, default=None)
#     clientid = models.CharField(max_length=50, default=None, null=True)
#     appdesc = models.CharField(max_length=50, default=None, null=True)
#     appver = models.CharField(max_length=10, default=None, null=True)
#     previous_port = models.IntegerField(default=0, blank=True)
#     manual_internal_port = models.IntegerField(default=None, null=True, blank=True)
#     enabled = models.BooleanField(default=True)
#
#     class Meta:
#         ordering = ['tunnelport__portnumber', ]
#
#     def __str__(self):
#         return str(self.tunnelport.portnumber) + " -- " + self.clientid
#
#     def get_internal_port(self):
#         if self.manual_internal_port and self.manual_internal_port != 0:
#             return self.manual_internal_port
#         if self.tunnelport:
#             return self.tunnelport.portnumber - 10000
#
#         return None
#
#     def find_open_port(self):
#         ports = TunnelPort.objects.filter(tunnelclient=None)
#         if len(ports) > 0:
#             return random.choice(ports)
#
#         return None
#
#
# @receiver(post_save, sender=TunnelClient)
# def post_save_tunnelclient(sender, instance=None, created=False, **kwargs):
#     if instance.tunnelport and instance.tunnelport.portnumber != instance.previous_port:
#         set_operation_dirty()
#         instance.previous_port = instance.tunnelport.portnumber
#         instance.save()
#     if created:
#         set_operation_dirty()


class TunnelClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    tunnelUrl = models.CharField(max_length=255, default=None, null=True)
    description = models.CharField(max_length=50, default=None, null=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.tunnelUrl)


class VLAN(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    number = models.IntegerField(default=0, blank=True)

    def __str__(self):
        if self.name:
            return str(self.number) + " : " + str(self.name)
        else:
            return str(self.number)


class Subnet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    subnet = models.CharField(max_length=50, default=None, null=True)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, blank=True, null=True)
    autoscan = models.BooleanField(default=True, blank=True)
    vlan = models.ForeignKey(VLAN, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return str(self.name)

    def get_usage(self):
        used = len(self.address_set.all())
        hsts = ipaddress.IPv4Network(self.subnet).hosts()
        usable = sum(1 for _ in hsts)
        return str(used) + "/" + str(usable) + " (" + str(round((used/usable)*100, 2)) + "% used)"


class Address(models.Model):
    class AddressStatus(models.IntegerChoices):
        UNKNOWN = 0, 'Unknown'
        RESERVED = 1, 'Reserved'
        IN_USE = 2, 'In Use'
        PLANNED = 3, 'Planned'
        OTHER = 4, 'Other'
        UNUSED = 5, 'Unused'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    description = models.CharField(max_length=50, default=None, null=True)
    subnet = models.ForeignKey(Subnet, on_delete=models.CASCADE, blank=False, null=True)
    address = models.CharField(max_length=50, default=None, null=True)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, blank=True, null=True)
    status = models.IntegerField(default=AddressStatus.UNKNOWN, choices=AddressStatus.choices)

    def __str__(self):
        return str(self.address)

    def get_status(self):
        return self.AddressStatus.choices[self.status][1]
