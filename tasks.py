
from celery_app import celery
from app import create_app
from app.services.twitter_service import TwitterService
from app.config import Config

app = create_app()
app.app_context().push()

ts = TwitterService(Config.RATELIMIT, Config.RATELIMIT_WINDOW)

@celery.task()
def post_tweet_async(text, media_id=None):
    return ts.post(text, media_id)
