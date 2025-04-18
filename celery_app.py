
from celery import Celery
import os

def make_celery(app_name="twitter_bot"):
    redis_url=os.getenv("REDIS_URL","redis://localhost:6379/0")
    return Celery(app_name, broker=redis_url, backend=redis_url)

celery = make_celery()

