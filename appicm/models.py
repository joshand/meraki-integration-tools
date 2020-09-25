from django.contrib.auth.models import User
import django.utils.timezone
from django.db import models
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


class BearerAuthentication(authentication.TokenAuthentication):
    """
    Simple token based authentication using utvsapitoken.

    Clients should authenticate by passing the token key in the 'Authorization'
    HTTP header, prepended with the string 'Bearer '.  For example:

        Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234
    """
    keyword = 'Bearer'


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


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


def get_default_tenant(obj=False):
    deften = Tenant.objects.filter(name="Default")
    if len(deften) == 1:
        if obj:
            return deften[0]
        else:
            return deften[0].id
    else:
        deften = Tenant.objects.create(name="Default")
        return deften


def get_file_path(instance, filename):
    ext = "." + filename.split('.')[-1]
    filename = string_generator(8) + ext
    return os.path.join('upload', filename)


class UploadZip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=255, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=True, null=True, default=None)
    file = models.FileField(upload_to=get_file_path)
    pkg_ver = models.FloatField(blank=True, default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
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


@receiver(post_save, sender=UploadZip)
def post_save_uploadzip(sender, instance=None, created=False, **kwargs):
    post_save.disconnect(post_save_uploadzip, sender=UploadZip)
    unzipped = zipfile.ZipFile(BytesIO(instance.file.read()))
    pkg = unzipped.read("package.json")
    pkg_json = json.loads(pkg.decode("utf-8"))
    instance.description = str(pkg_json.get("name", str(instance.file.name)))
    instance.pkg_ver = float(pkg_json.get("version", 0.0))
    if not instance.tenant:
        instance.tenant = get_default_tenant(obj=True)
    instance.save()
    for p in pkg_json.get("files", []):
        p_target = p.get("target", "")
        p_file = p.get("file", "")
        print(p_target, p_file)
        fp = "upload"
        ext = ".json"
        if p_target == "scripts":
            fp = "scripts"
            ext = ".py"

        fn = fp + "/f" + string_generator(8) + ext
        if p_target == "database":
            bfd = unzipped.read(p_file).decode("utf-8").replace("{{tenant}}", str(instance.tenant.id))
            open(fn, 'wb').write(bfd.encode("utf-8"))
        else:
            open(fn, 'wb').write(unzipped.read(p_file))

        i = Upload.objects.create(description=p_file, type=p_target, file=fn, uploadzip=instance)
        i.save()

        if p_target == "database":
            management.call_command('loaddata', fn)

        # for libitem in unzipped.namelist():
        #     if libitem.startswith('')
        #     if libitem.startswith('__MACOSX/'):
        #         continue
        #     fn = "upload/" + libitem
        #     open(fn, 'wb').write(unzipped.read(libitem))
        #     i = Upload.objects.create(description=instance.description + "-" + fn, file=fn)
        #     i.save()

    post_save.connect(post_save_uploadzip, sender=UploadZip)


@receiver(models.signals.post_delete, sender=UploadZip)
def auto_delete_uploadzip_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `UploadZip` object is deleted.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)


@receiver(models.signals.pre_save, sender=UploadZip)
def auto_delete_uploadzip_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem
    when corresponding `UploadZip` object is updated
    with new file.
    """
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
    file = models.FileField(upload_to='upload')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=10, blank=True, null=True, default=None)
    uploadzip = models.ForeignKey(UploadZip, on_delete=models.CASCADE, null=True, default=None)

    def __str__(self):
        return self.description

    def filedata(self):
        try:
            try:
                return self.file.read().decode("utf-8")
            except Exception:
                return self.file.read()
        except Exception:
            return self.file

    def fspath(self):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), self.file.name)

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
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)


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
    name = models.CharField(max_length=50)
    device_type = models.CharField(max_length=50, null=True, blank=True, default=None)
    portcount = models.IntegerField(null=True, blank=True, default=None)
    portlist = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return self.name


class DeviceType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    py_mod_name = models.CharField(max_length=30)
    authtype = models.ForeignKey(AuthType, on_delete=models.CASCADE)
    defaultmgmtaddress = models.CharField(max_length=100, default="", null=True, blank=True)
    supportscontroller = models.BooleanField("Is Controller / Management System?", default=False)
    parmdef = models.JSONField(default=dict)

    def __str__(self):
        return self.name


class Controller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    devicetype = models.ForeignKey(DeviceType, on_delete=models.CASCADE)
    authparm = models.JSONField(default=dict)
    mgmtaddress = models.CharField(max_length=100, default="", null=True, blank=True)
    rawdata = models.JSONField(blank=True, default=None, null=True)

    def __str__(self):
        return self.name


class Device(models.Model):
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

    def __str__(self):
        return str(self.name) + " -- " + str(self.serial_number) + " (" + str(self.devicemodeltype) + ")"


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
    rawdata = models.JSONField(editable=False)

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


class TaskResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, null=True)
    taskname = models.CharField(max_length=30)
    runtime = models.DateTimeField(auto_now=True)
    result = models.TextField(null=True)

    class Meta:
        ordering = ['-runtime']

    def __str__(self):
        return str(self.runtime) + " -- " + str(self.taskname)


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
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=50, null=True, default=None)
    entity_name = models.CharField(max_length=30, null=True, default=None)
    entity_name_plural = models.CharField(max_length=30, null=True, default=None)
    py_mod_name = models.CharField(max_length=30, null=True, default=None)
    sync_interval = models.IntegerField(null=True, blank=True, default=60)
    devicetype = models.ForeignKey(DeviceType, on_delete=models.SET_NULL, null=True, default=None)
    default_icon = models.CharField(max_length=250, null=True, default=None)

    def __str__(self):
        return self.name


class Construct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    constructId = models.CharField(max_length=50, default=None, null=True)
    type = models.CharField(max_length=50, default=None, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    rawdata = models.JSONField(editable=False)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, blank=False, null=True)

    def __str__(self):
        return self.type + ":" + self.name


class Tunnel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    tunnelId = models.CharField(max_length=50, default=None, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    rawdata = models.JSONField(editable=False)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, blank=False, null=True)

    def __str__(self):
        return str(self.name)


class IntegrationModule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    name = models.CharField(max_length=50, default=None, null=True)
    description = models.CharField(max_length=50, null=True, default=None)
    notes = models.TextField(null=True, blank=True, default=None)
    pm1 = models.ForeignKey(PluginModule, related_name="pm1", on_delete=models.SET_NULL, null=True)
    pm2 = models.ForeignKey(PluginModule, related_name="pm2", on_delete=models.SET_NULL, null=True)
    py_mod_name = models.CharField(max_length=30, default=None, null=True)
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
        return str(self.integrationmodule.name)
