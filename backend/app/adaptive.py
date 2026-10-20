from dataclasses import dataclass
from enum import Enum
import time

class State(str, Enum):
    NORMAL="NORMAL"
    WARNING="WARNING"
    HIGH_LOAD="HIGH_LOAD"
    CRITICAL="CRITICAL"

@dataclass
class Telemetry:
    cpu: float = 0
    memory: float = 0
    queue: float = 0
    latency_ms: float = 0
    throughput: float = 0
    active: int = 0
    error_rate: float = 0

class AdaptiveController:
    def __init__(self, min_rate, max_rate, initial_rate, cooldown=3):
        self.min_rate=min_rate
        self.max_rate=max_rate
        self.rate=initial_rate
        self.cooldown=cooldown
        self.state=State.NORMAL
        self.last_change=0
        self._smooth = Telemetry()

    def _ema(self, old, new, alpha=.25):
        return old*(1-alpha)+new*alpha

    def update(self, t: Telemetry):
        self._smooth = Telemetry(
            cpu=self._ema(self._smooth.cpu,t.cpu),
            memory=self._ema(self._smooth.memory,t.memory),
            queue=self._ema(self._smooth.queue,t.queue),
            latency_ms=self._ema(self._smooth.latency_ms,t.latency_ms),
            throughput=self._ema(self._smooth.throughput,t.throughput),
            active=int(self._ema(self._smooth.active,t.active)),
            error_rate=self._ema(self._smooth.error_rate,t.error_rate),
        )
        s=self._smooth
        if s.cpu>=90 or s.memory>=90 or s.queue>=90 or s.latency_ms>=1000 or s.error_rate>=20:
            state=State.CRITICAL
        elif s.cpu>=75 or s.memory>=80 or s.queue>=70 or s.latency_ms>=500 or s.error_rate>=10:
            state=State.HIGH_LOAD
        elif s.cpu>=60 or s.memory>=70 or s.queue>=40 or s.latency_ms>=250 or s.error_rate>=5:
            state=State.WARNING
        else:
            state=State.NORMAL
        now=time.monotonic()
        if now-self.last_change >= self.cooldown:
            if state==State.NORMAL:
                self.rate=min(self.max_rate, self.rate*1.10)
            elif state==State.WARNING:
                self.rate=max(self.min_rate, self.rate*.90)
            elif state==State.HIGH_LOAD:
                self.rate=max(self.min_rate, self.rate*.70)
            else:
                self.rate=max(self.min_rate, self.rate*.50)
            self.last_change=now
        self.state=state
        return self.rate, state
