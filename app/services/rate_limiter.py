
from collections import deque
from datetime import datetime, timedelta

class RateLimiter:
    """Sliding‑window limiter. returns (allowed, remaining/time)."""
    def __init__(self, max_requests:int, window:int):
        self.max_requests=max_requests
        self.window=window
        self.req=deque()

    def can_request(self):
        now=datetime.now()
        while self.req and self.req[0] < now - timedelta(seconds=self.window):
            self.req.popleft()
        remaining=self.max_requests-len(self.req)
        if remaining>0:
            self.req.append(now)
            return True, remaining
        wait=(self.req[0]+timedelta(seconds=self.window)-now).total_seconds()
        return False, wait
