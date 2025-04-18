
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
                
# process failed queue
from app.models import FailedPostQueue
q_items=FailedPostQueue.query.limit(10).all()
for item in q_items:
    res=ts.post_async(item.content)
    if res.get("status")=="success":
        db.session.delete(item)
    else:
        item.tries+=1
        if item.tries>=5:
            db.session.delete(item)
    db.session.commit()

                if processed:
                    logging.info("Processed %s scheduled tweets", len(processed))
            except Exception as e:
                logging.error("Scheduler error %s", e)
            time.sleep(60)

if __name__=="__main__":
    run_scheduler()
