from celery import shared_task


@shared_task
def add(x, y):
    """Simple test task — returns x + y."""
    return x + y
