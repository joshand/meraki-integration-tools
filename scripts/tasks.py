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


cron = BackgroundScheduler()


def run():
    # Explicitly kick off the background thread
    try:
        cron.start()
    except Exception:
        # scheduler may already be running
        pass
    cron.remove_all_jobs()

    tenant_list = []
    tenants = Tenant.objects.exclude(id=get_default_tenant())
    for tenant in tenants:
        tenant_list.append(str(tenant.id))
    tenant_map = {}

    for x in range(0, 4):
        pms = []
        mode = "check"
        if x == 0:
            # Run plugin modules for any tenant that has them installed; each job will be unique to a single tenant
            pms = PluginModule.objects.exclude(id=get_default_tenant())
            mode = "add"
        elif x == 1:
            # Run integration modules for any tenant that has them installed; each job will be unique to a single tenant
            pms = IntegrationModule.objects.exclude(id=get_default_tenant())
            mode = "add"
        elif x == 2:
            # Run global plugin modules for remaining tenants
            pms = PluginModule.objects.filter(id=get_default_tenant())
            mode = "check"
        elif x == 3:
            # Run global integration modules for remaining tenants
            pms = IntegrationModule.objects.filter(id=get_default_tenant())
            mode = "check"

        for pm in pms:
            if mode == "add":
                if pm.name in tenant_map:
                    tenant_map[pm.name].remove(str(pm.tenant.id))
                else:
                    tenant_map[pm.name] = tenant_list
                    if str(pm.tenant.id) in tenant_map[pm.name]:
                        tenant_map[pm.name].remove(str(pm.tenant.id))
            else:
                if str(pm.tenant.id) not in tenant_map[pm.name]:
                    # if it's been removed from the map, it's already had a module ran
                    continue

            pmn = get_script(pm)
            if not pmn:
                continue
            jobname = pmn + ".do_sync"
            try:
                globals()[pmn] = __import__(pmn)
            except Exception:
                print("Exception loading module", pm)
                continue
            job = eval(jobname)
            # print(pmn, job, pm.sync_interval)
            cron.add_job(job, 'interval', kwargs={"tenant_list": [str(pm.tenant.id)]}, seconds=pm.sync_interval)

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
