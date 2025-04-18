
#!/usr/bin/env python3
import time, logging
from app import create_app
from app.services.twitter_service import TwitterService
from app.config import Config

def run_scheduler():
    app=create_app()
    with app.app_context():
        ts=TwitterService(Config.RATELIMIT, Config.RATELIMIT_WINDOW)
        while True:
            try:
                processed=ts.process_scheduled_tweets()
                if processed:
                    logging.info("Processed %s scheduled tweets", len(processed))
            except Exception as e:
                logging.error("Scheduler error %s", e)
            time.sleep(60)

if __name__=="__main__":
    run_scheduler()
