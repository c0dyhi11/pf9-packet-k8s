from celery import Celery
from celery import signals


@signals.setup_logging.connect
def setup_celery_logging(**kwargs):
    pass


app = Celery('celery_config', include=['async_tasks'], broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0')
