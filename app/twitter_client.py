import os, logging, tweepy
from .rate_limiter import RateLimiter
from .metrics import metrics

class TwitterClient:
    def __init__(self, max_requests:int, time_window:int):
        self.rate_limiter = RateLimiter(max_requests,time_window)
        self.client = tweepy.Client(
            bearer_token=os.getenv("BEARER_TOKEN"),
            consumer_key=os.getenv("API_KEY"),
            consumer_secret=os.getenv("API_KEY_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )
        try:
            self.client.get_user(username="twitter")  # test connection
            logging.info("✅ Conectado à API v2 do X.")
        except Exception as e:
            logging.error("Falha na autenticação: %s", e)
            raise

    def post_tweet(self, text:str):
        if not self.rate_limiter.can_request():
            metrics.rate_limit_hits +=1
            return {"status":"error","message":"Limite diário atingido."}
        try:
            self.client.create_tweet(text=text)
            metrics.posts_success +=1
            return {"status":"success","message":"Tweet publicado."}
        except tweepy.errors.Forbidden:
            metrics.posts_failed +=1
            return {"status":"error","message":"Permissão negada. Verifique credenciais."}
        except tweepy.errors.TooManyRequests:
            metrics.rate_limit_hits +=1
            return {"status":"error","message":"Rate limit. Tente mais tarde."}
        except Exception as e:
            metrics.posts_failed +=1
            logging.exception("Erro inesperado ao postar")
            return {"status":"error","message":f"Erro inesperado: {e}"}