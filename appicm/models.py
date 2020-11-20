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


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)

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
    fp = os.path.join('upload', filename)
    fp = os.path.join(settings.BASE_DIR, fp)
    return fp


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
    logdata = ""
    post_save.disconnect(post_save_uploadzip, sender=UploadZip)
    unzipped = zipfile.ZipFile(BytesIO(instance.file.read()))
    pkg = unzipped.read("package.json")
    pkg_json = json.loads(pkg.decode("utf-8"))
    desc = str(pkg_json.get("name", str(instance.file.name)))
    logdata += "description=" + str(desc) + "\n"
    instance.description = desc
    pkg_ver = float(pkg_json.get("version", 0.0))
    logdata += "version=" + str(pkg_ver) + "\n"
    instance.pkg_ver = pkg_ver
    if not instance.tenant:
        instance.tenant = get_default_tenant(obj=True)
    logdata += "tenant=" + str(instance.tenant) + "\n"
    instance.save()
    for p in pkg_json.get("files", []):
        logdata += "processing entry=" + str(p) + "\n"
        p_target = p.get("target", "")
        p_file = p.get("file", "")
        logdata += "target=" + str(p_target) + "\n"
        logdata += "file=" + str(p_file) + "\n"
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
        if p_target == "database":
            bfd = unzipped.read(p_file).decode("utf-8").replace("{{tenant}}", str(instance.tenant.id))
            open(fn, 'wb').write(bfd.encode("utf-8"))
        else:
            open(fn, 'wb').write(unzipped.read(p_file))

        try:
            i = Upload.objects.create(description=p_file, type=p_target, file=fn, uploadzip=instance,
                                      tenant=instance.tenant)
            i.save()
            logdata += "upload object=" + str(i) + "\n"
        except Exception as e:
            logdata += "exception uploading object=" + str(e) + "\n"

        if p_target == "database":
            management.call_command('loaddata', fn)


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


@receiver(models.signals.post_delete, sender=UploadZip)
def auto_delete_uploadzip_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `UploadZip` object is deleted.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
    set_operation_dirty()


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
    named_id = models.CharField(max_length=100, default=None, null=True)
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
    rawdata = models.JSONField(blank=True, null=True, default=None)
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
    rawdata = models.JSONField(blank=True, null=True, default=None)
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
    rawdata = models.JSONField(blank=True, null=True, default=None)
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
    rawdata = models.JSONField(blank=True, null=True, default=None)
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
    rawdata = models.JSONField(blank=True, null=True, default=None)
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
    name = models.CharField(max_length=20, blank=False)
    icon = models.CharField(max_length=20, blank=True, default="icon-3d-object_20")

    def __str__(self):
        return self.name


class CustomTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
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
    rawdata = models.JSONField(editable=False)
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, blank=True, null=True)
    integrationconfiguration = models.ForeignKey(IntegrationConfiguration, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return self.type + ":" + self.name


class TunnelPort(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portnumber = models.IntegerField(default=0)

    class Meta:
        ordering = ['portnumber', ]

    def __str__(self):
        return str(self.portnumber)


class TunnelClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=False, default=get_default_tenant, null=True)
    tunnelport = models.ForeignKey(TunnelPort, on_delete=models.SET_NULL, blank=True, null=True)
    descriptioon = models.CharField(max_length=50, default=None, null=True)
    pid = models.IntegerField(default=0, blank=True)
    log = models.TextField(null=True, blank=True, default=None)
    clientid = models.CharField(max_length=50, default=None, null=True)
    appdesc = models.CharField(max_length=50, default=None, null=True)
    appver = models.CharField(max_length=10, default=None, null=True)
    previous_port = models.IntegerField(default=0, blank=True)
    manual_internal_port = models.IntegerField(default=None, null=True, blank=True)

    class Meta:
        ordering = ['tunnelport__portnumber', ]

    def __str__(self):
        return str(self.tunnelport.portnumber) + " -- " + self.clientid

    def get_internal_port(self):
        if self.manual_internal_port and self.manual_internal_port != 0:
            return self.manual_internal_port
        if self.tunnelport:
            return self.tunnelport.portnumber - 10000

        return None

    def find_open_port(self):
        ports = TunnelPort.objects.filter(tunnelclient=None)
        if len(ports) > 0:
            return random.choice(ports)

        return None


@receiver(post_save, sender=TunnelClient)
def post_save_tunnelclient(sender, instance=None, created=False, **kwargs):
    if instance.tunnelport and instance.tunnelport.portnumber != instance.previous_port:
        set_operation_dirty()
        instance.previous_port = instance.tunnelport.portnumber
        instance.save()
    if created:
        set_operation_dirty()
