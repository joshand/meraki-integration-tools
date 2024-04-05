# import sys
# import os
# from django_apscheduler.models import DjangoJob
# from apscheduler.schedulers.background import BackgroundScheduler
# from django_apscheduler.jobstores import DjangoJobStore
# # from django_apscheduler.jobstores import register_events
# import scripts.dashboard
# # import scripts.ise_monitor
# # import scripts.clean_tasks
# # import scripts.pxgrid_websocket
# # import scripts.dashboard_webhook  # noqa: F401
# # import scripts.db_backup  # noqa: F401
#
# scheduler = BackgroundScheduler()
# scheduler.add_jobstore(DjangoJobStore(), "default")
#
#
# def run():     # pragma: no cover
#     scheduler.add_job(scripts.dashboard.sync_dashboard, "interval", id="dashboard_monitor", seconds=60,
#                       replace_existing=True)
#     # scheduler.add_job(scripts.ise_monitor.sync_ise, "interval", id="ise_monitor", seconds=10, replace_existing=True)
#     # scheduler.add_job(scripts.clean_tasks.cleanup, "interval", id="clean_tasks", hours=8, replace_existing=True)
#     # scheduler.add_job(scripts.db_backup.backup, "interval", id="db_backup", hours=24, replace_existing=True)
#
#     scheduler.start()
#     while True:
#         pass


import atexit
from apscheduler.schedulers.background import BackgroundScheduler
# import scripts.dashboard
import scripts
from appicm.models import *
from scripts.common import get_script
# from scripts.tunnels import start_tunnel, stop_tunnel, health_check
from datetime import datetime, timedelta
from . import ws_server
from . import ws_api_gw

cron = BackgroundScheduler()
# ws = ws_server.WebsocketServer


def check_operation():
    operations = Operation.objects.all()
    if len(operations) == 0:
        Operation.objects.create(reload_tasks=False)
    elif len(operations) > 0:
        if operations[0].reload_tasks:
            TaskResult.objects.create(tenant=get_default_tenant(obj=True), taskname="task_scheduler", result="reloaded tasks")
            operations[0].reload_tasks = False
            operations[0].save()
            start()


# def tunnel_health_check():
#     tcs = TunnelClient.objects.all()
#     for tc in tcs:
#         if not tc.enabled:
#             TaskResult.objects.create(tenant=tc.tenant, taskname="tunnel_manager",
#                                       result="tunnel is disabled:" + str(tc))
#             if tc.pid != 0:
#                 stop_tunnel(tc)
#             continue
#
#         state, result = health_check(tc.get_internal_port())
#         if not state:
#             TaskResult.objects.create(tenant=tc.tenant, taskname="tunnel_manager",
#                                       result="failed;" + str(state) + ";" + str(result) + ";restarting tunnel:" + str(tc))
#             stop_tunnel(tc)
#             time.sleep(5)
#             start_tunnel(tc)
#         else:
#             TaskResult.objects.create(tenant=tc.tenant, taskname="tunnel_manager",
#                                       result="success" + str(state) + ";" + str(result) + ";tunnel:" + str(tc))
#

def log_cleanup():
    time_threshold = datetime.now() - timedelta(hours=4)
    TaskResult.objects.filter(runtime__lt=time_threshold).delete()


def start():
    # Explicitly kick off the background thread
    try:
        cron.start()
        # ws_server.go()
        # ws_api_gw.go()
    except Exception:
        # scheduler may already be running
        pass
    cron.remove_all_jobs()
    cron.add_job(log_cleanup, 'interval', hours=1)
    cron.add_job(check_operation, 'interval', seconds=60)
    # cron.add_job(tunnel_health_check, 'interval', seconds=60)
    #
    # tcs = TunnelClient.objects.all()
    # for tc in tcs:
    #     if tc.pid:
    #         stop_tunnel(tc)
    # #         tc.pid = 0
    # #         tc.save()
    # # time.sleep(1)
    # for tc in tcs:
    #     job = cron.add_job(start_tunnel, args=[tc])

    tenant_list = []
    tenants = Tenant.objects.exclude(id=get_default_tenant())
    for tenant in tenants:
        tenant_list.append(str(tenant.id))
    tenant_map = {}

    mode = "none"
    for x in range(0, 4):
        pms = []
        if x == 0:
            # Run plugin modules for any tenant that has them installed; each job will be unique to a single tenant
            pms = PluginModule.objects.exclude(tenant_id=get_default_tenant()).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
            mode = "tenant"
        elif x == 1:
            # Run integration modules for any tenant that has them installed; each job will be unique to a single tenant
            pms = IntegrationModule.objects.exclude(tenant_id=get_default_tenant()).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
            mode = "tenant"
        elif x == 2:
            # Run global plugin modules for remaining tenants
            pms = PluginModule.objects.filter(tenant_id=get_default_tenant()).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
            mode = "global"
        elif x == 3:
            # Run global integration modules for remaining tenants
            pms = IntegrationModule.objects.filter(tenant_id=get_default_tenant()).exclude(plugin_id__isnull=True).exclude(plugin_id__exact='')
            mode = "global"

        # print(x, mode, pms)
        for pm in pms:
            if mode == "tenant":
                if pm.name in tenant_map:
                    try:
                        tenant_map[pm.name].remove(str(pm.tenant.id))
                    except Exception:
                        print("Unable to remove", str(pm.tenant.id))
                else:
                    tenant_map[pm.name] = tenant_list
                    if str(pm.tenant.id) in tenant_map[pm.name]:
                        tenant_map[pm.name].remove(str(pm.tenant.id))
            else:
                if pm.name not in tenant_map:
                    # if the module name isn't there, no tenants had that individual module
                    pass
                elif str(pm.tenant.id) not in tenant_map[pm.name]:
                    # if it's been removed from the map, it's already had a module ran
                    continue

            pmn = get_script(pm)
            # print(pm, pmn, tenant_map)
            if not pmn:
                continue
            jobname = pmn + ".do_sync"
            try:
                globals()[pmn] = __import__(pmn)
                job = eval(jobname)
            except Exception:
                print("Exception loading module", pm)
                continue
            # print(pmn, job, pm.sync_interval)
            if pm.sync_interval == 0:
                if mode == "tenant":
                    cron.add_job(job, kwargs={"tenant_list": [str(pm.tenant.id)]})
                else:
                    cron.add_job(job)
            else:
                if mode == "tenant":
                    cron.add_job(job, 'interval', kwargs={"tenant_list": [str(pm.tenant.id)]}, seconds=pm.sync_interval)
                else:
                    cron.add_job(job, 'interval', seconds=pm.sync_interval)

    # ims = IntegrationModule.objects.all()
    # for im in ims:
    #     pmn = get_script(im)
    #     if not pmn:
    #         continue
    #     jobname = pmn + ".do_sync"
    #     try:
    #         globals()[pmn] = __import__(pmn)
    #     except Exception:
    #         print("Exception loading module", im)
    #         continue
    #     job = eval(jobname)
    #     # print(pmn, job, pm.sync_interval)
    #     cron.add_job(job, 'interval', seconds=im.sync_interval)

    # job1 = cron.add_job(scripts.dashboard.do_sync, 'interval', seconds=60)
    # job2 = cron.add_job(scripts.network_monitor.run, 'interval', seconds=30)
    # job3 = cron.add_job(scripts.client_monitor.run, 'interval', seconds=30)
    # job4 = cron.add_job(scripts.clean_tasks.run, 'interval', minutes=60)

    # Shutdown your cron thread if the web process is stopped
    atexit.register(lambda: cron.shutdown(wait=False))


def run():
    start()

    while True:
        pass
