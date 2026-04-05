import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Kotoback.settings')

app = Celery('Kotoback')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat schedule for cleanup tasks
app.conf.beat_schedule = {
    'cleanup-old-ingestion-jobs': {
        'task': 'book.tasks.cleanup_old_ingestion_jobs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-orphaned-epubs': {
        'task': 'book.tasks.cleanup_orphaned_epubs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
