
import os, logging, tweepy, datetime
from .rate_limiter import RateLimiter
from ..models import PostHistory
from .. import db, cache

class TwitterService:
    def __init__(self,rate_limit,window):
        self.client=tweepy.Client(
            bearer_token=os.getenv("BEARER_TOKEN"),
            consumer_key=os.getenv("API_KEY"),
            consumer_secret=os.getenv("API_KEY_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True)
        self.limiter=RateLimiter(rate_limit,window)
    def post(self,text):
        if not self.limiter.can_request():
            return {"status":"error","message":"Rate limit hit"}
        res=self.client.create_tweet(text=text)
        tweet_id=res.data.get("id")
        hist=PostHistory(content=text,tweet_id=tweet_id)
        db.session.add(hist);db.session.commit()
        return {"status":"success","message":"Tweeted","id":tweet_id}
    def fetch_metrics(self,tweet_id):
        try:
            tweet=self.client.get_tweet(tweet_id,tweet_fields=["public_metrics"]).data
            m=tweet.public_metrics
            return m
        except Exception as e:
            logging.error("metric fetch error %s",e)
            return {}
    @cache.cached(timeout=600)
    def content_pool(self,name):
        import json, pathlib
        path=pathlib.Path(__file__).parent.parent/ "content"/ f"{name}.json"
        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)
