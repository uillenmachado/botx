#!/usr/bin/env python3
"""
Scheduler daemon for processing scheduled tweets and retry queue.
Run with: python scheduler.py
"""
import time
import logging

from app import create_app, db
from app.services.twitter_service import TwitterService
from app.models import FailedPostQueue
from app.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_failed_queue(ts):
    """Process failed posts queue with retry logic"""
    q_items = FailedPostQueue.query.limit(10).all()
    
    for item in q_items:
        res = ts.post(item.content)
        
        if res.get("status") == "success":
            db.session.delete(item)
            logger.info("Retry successful for queued post: %s", item.id)
        else:
            item.tries += 1
            if item.tries >= 5:
                db.session.delete(item)
                logger.warning("Removed post after 5 failed attempts: %s", item.id)
        
        db.session.commit()


def run_scheduler():
    """Main scheduler loop"""
    app = create_app()
    
    with app.app_context():
        ts = TwitterService(Config.RATELIMIT, Config.RATELIMIT_WINDOW)
        logger.info("Scheduler started")
        
        while True:
            try:
                # Process scheduled tweets
                processed = ts.process_scheduled_tweets()
                if processed:
                    logger.info("Processed %s scheduled tweets", len(processed))
                
                # Process failed queue
                process_failed_queue(ts)
                
            except Exception as e:
                logger.error("Scheduler error: %s", e)
            
            time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
