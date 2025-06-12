import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_calls, period_seconds):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self.call_timestamps = deque()

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # Remove timestamps older than the period
            while self.call_timestamps and self.call_timestamps[0] < time.time() - self.period_seconds:
                self.call_timestamps.popleft()

            if len(self.call_timestamps) >= self.max_calls:
                sleep_duration = (self.call_timestamps[0] + self.period_seconds) - time.time()
                if sleep_duration > 0:
                    logger.info(f"Rate limit exceeded for {func.__name__}. Sleeping for {sleep_duration:.2f} seconds.")
                    time.sleep(sleep_duration)

            self.call_timestamps.append(time.time())
            return func(*args, **kwargs)
        return wrapper
