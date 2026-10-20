import asyncio, time
from collections import deque
from abc import ABC, abstractmethod

class RateLimiter(ABC):
    @abstractmethod
    async def allow(self, key: str, cost: int = 1) -> bool: ...

class TokenBucket(RateLimiter):
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets = {}
        self.lock = asyncio.Lock()

    async def allow(self, key: str, cost: int = 1) -> bool:
        async with self.lock:
            now = time.monotonic()
            tokens, last = self.buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
            if tokens >= cost:
                self.buckets[key] = (tokens - cost, now)
                return True
            self.buckets[key] = (tokens, now)
            return False

    def utilization(self, key="global"):
        tokens, _ = self.buckets.get(key, (self.capacity, time.monotonic()))
        return max(0.0, min(100.0, (1 - tokens / self.capacity) * 100))

class LeakyBucket(RateLimiter):
    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.queues = {}
        self.last = {}
        self.lock = asyncio.Lock()

    async def allow(self, key: str, cost: int = 1) -> bool:
        async with self.lock:
            now = time.monotonic()
            q = self.queues.setdefault(key, deque())
            last = self.last.get(key, now)
            elapsed = now - last
            drain = int(elapsed * self.leak_rate)
            for _ in range(min(drain, len(q))):
                q.popleft()
            self.last[key] = now
            if len(q) + cost <= self.capacity:
                for _ in range(cost):
                    q.append(now)
                return True
            return False

    def queue_length(self, key="global"):
        return len(self.queues.get(key, ()))

class RateLimiterManager:
    def __init__(self, config):
        self.config = config
        self.algorithm = config.algorithm
        self._build()

    def _build(self):
        if self.algorithm == "TOKEN_BUCKET":
            self.limiter = TokenBucket(self.config.bucket_capacity, self.config.refill_rate)
        else:
            self.limiter = LeakyBucket(self.config.queue_capacity, self.config.leak_rate)

    def switch(self, algorithm):
        self.algorithm = algorithm
        self.config.algorithm = algorithm
        self._build()

    async def allow(self, key):
        return await self.limiter.allow(key)

    def utilization(self, key="global"):
        if self.algorithm == "TOKEN_BUCKET":
            return self.limiter.utilization(key)
        q = self.limiter.queue_length(key)
        return min(100.0, q / self.config.queue_capacity * 100)
