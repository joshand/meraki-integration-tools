from django.apps import AppConfig
import os


class AppicmConfig(AppConfig):
    name = 'appicm'

    def ready(self):
        if os.environ.get('RUN_MAIN', None):
            import scripts.tasks
            scripts.tasks.start()
