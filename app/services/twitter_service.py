
import os, logging, tweepy, datetime
from .rate_limiter import RateLimiter
from ..models import PostHistory, ScheduledPost, db
from flask_caching import cache

class TwitterService:
    def __init__(self, rate_limit, window):
        required=[ "BEARER_TOKEN","API_KEY","API_KEY_SECRET","ACCESS_TOKEN","ACCESS_TOKEN_SECRET" ]
        missing=[t for t in required if not os.getenv(t)]
        if missing:
            raise ValueError(f"Missing Twitter API tokens: {', '.join(missing)}")
        self.limiter=RateLimiter(rate_limit,window)
        self.client=tweepy.Client(
            bearer_token=os.getenv("BEARER_TOKEN"),
            consumer_key=os.getenv("API_KEY"),
            consumer_secret=os.getenv("API_KEY_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )

    def validate_tweet_content(self, content):
        if not content or not content.strip():
            return False, "Empty content"
        if len(content) > 280:
            return False, f"More than 280 characters ({len(content)})"
        return True, ""

    def post(self, text):
        valid,msg=self.validate_tweet_content(text)
        if not valid:
            return {"status":"error","message":msg}
        allowed,info=self.limiter.can_request()
        if not allowed:
            return {"status":"error","message":f"Rate limit, wait {int(info)}s"}
        try:
            res=self.client.create_tweet(text=text)
            tweet_id=res.data.get("id")
            hist=PostHistory(content=text,tweet_id=tweet_id)
            db.session.add(hist);db.session.commit()
            return {"status":"success","message":"Tweeted","id":tweet_id}
        except tweepy.TweepyException as e:
            logging.error("Twitter API error: %s",e)
            
except tweepy.TooManyRequests as e:
    logging.warning("Rate limit hit, queueing tweet")
    from ..models import FailedPostQueue
    db.session.add(FailedPostQueue(content=text))
    db.session.commit()
    return {"status":"error","message":"Queued due to rate limit"}

            return {"status":"error","message":f"Error posting tweet: {str(e)}"}

    def process_scheduled_tweets(self):
        now=datetime.datetime.now().strftime('%H:%M')
        scheduled=ScheduledPost.query.filter_by(sent=False,time=now).all()
        results=[]
        for post in scheduled:
            result=self.post(post.content)
            if result.get("status")=="success":
                post.sent=True
                db.session.commit()
            results.append({"post":post.content,"result":result})
        return results

    @cache.cached(timeout=600)
    def content_pool(self, name):
        import json, pathlib
        path=pathlib.Path(__file__).parent.parent/ "content"/ f"{name}.json"
        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)

    def fetch_metrics(self, tweet_id):
        try:
            tweet=self.client.get_tweet(tweet_id,tweet_fields=["public_metrics","created_at"]).data
            m=tweet.public_metrics
            m["created_at"]=tweet.created_at
            post=PostHistory.query.filter_by(tweet_id=tweet_id).first()
            if post:
                post.likes=m.get("like_count",0)
                post.retweets=m.get("retweet_count",0)
                db.session.commit()
            return m
        except Exception as e:
            logging.error("Metric fetch error %s",e)
            return {}

def upload_image(self, file_path:str):
    """Upload image (PNG/JPG/GIF) via v1.1 media endpoint and return media_id"""
    import tweepy
    auth = tweepy.OAuth1UserHandler(
        os.getenv("API_KEY"), os.getenv("API_KEY_SECRET"),
        os.getenv("ACCESS_TOKEN"), os.getenv("ACCESS_TOKEN_SECRET")
    )
    api = tweepy.API(auth, wait_on_rate_limit=True)
    try:
        media = api.media_upload(file_path)
        return media.media_id_string
    except tweepy.TweepyException as e:
        logging.error("Media upload error: %s", e)
        return None

def post_async(self, text, media_id=None):
    from tasks import post_tweet_async
    post_tweet_async.delay(text, media_id)
    return {"status":"queued","message":"Tweet enfileirado para envio"}
