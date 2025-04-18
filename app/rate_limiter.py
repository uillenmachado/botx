from collections import deque
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests:int, time_window:int):
        self.max_requests=max_requests
        self.time_window=time_window
        self.requests=deque()

    def can_request(self)->bool:
        now=datetime.now()
        while self.requests and self.requests[0] < now - timedelta(seconds=self.time_window):
            self.requests.popleft()
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False