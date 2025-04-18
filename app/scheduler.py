import schedule, threading, time, logging
from datetime import datetime
from .metrics import metrics

jobs=[]

def add_job(content:str, time_str:str, callback):
    schedule.every().day.at(time_str).do(callback, content)
    jobs.append({"post":content,"time":time_str})
    metrics.scheduled +=1

def run():
    def _runner():
        while True:
            schedule.run_pending()
            time.sleep(30)
    threading.Thread(target=_runner,daemon=True).start()

def cancel_job(time_str:str):
    for job in list(schedule.jobs):
        if job.at_time == time_str:
            schedule.cancel_job(job)