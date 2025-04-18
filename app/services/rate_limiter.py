
from collections import deque
from datetime import datetime, timedelta
class RateLimiter:
    def __init__(self,max_requests,window):
        self.max_requests=max_requests
        self.window=window
        self.req=deque()
    def can_request(self):
        now=datetime.now()
        while self.req and self.req[0] < now - timedelta(seconds=self.window):
            self.req.popleft()
        if len(self.req)<self.max_requests:
            self.req.append(now)
            return True
        return False
