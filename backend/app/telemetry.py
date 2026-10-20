import asyncio, time, psutil
from collections import deque
from .adaptive import Telemetry

class TelemetryService:
    def __init__(self, interval=1):
        self.interval=interval
        self.started=time.monotonic()
        self.total=0; self.accepted=0; self.rejected=0; self.throttled=0
        self.latencies=deque(maxlen=1000)
        self.status_counts={"2xx":0,"4xx":0,"5xx":0}
        self.active=0
        self.history=deque(maxlen=300)
        self._last_total=0

    def record(self, accepted, latency_ms, status):
        self.total+=1
        self.accepted += int(accepted)
        self.rejected += int(not accepted)
        self.latencies.append(latency_ms)
        self.status_counts[f"{status//100}xx"] = self.status_counts.get(f"{status//100}xx",0)+1

    def snapshot(self, rate_limit, queue_length=0, bucket_utilization=0, state="NORMAL", algorithm="TOKEN_BUCKET"):
        now=time.time()
        rps=self.total-self._last_total
        self._last_total=self.total
        lat=sorted(self.latencies)
        avg=sum(lat)/len(lat) if lat else 0
        p95=lat[min(len(lat)-1,int(len(lat)*.95))] if lat else 0
        snap={
            "timestamp":now,"requests_per_sec":rps,"total_requests":self.total,
            "accepted_requests":self.accepted,"rejected_requests":self.rejected,
            "throttled_requests":self.throttled,"avg_latency_ms":round(avg,2),
            "p95_latency_ms":round(p95,2),"cpu_utilization":psutil.cpu_percent(),
            "memory_utilization":psutil.virtual_memory().percent,"active_requests":self.active,
            "queue_length":queue_length,"current_rate_limit":round(rate_limit,2),
            "bucket_utilization":round(bucket_utilization,2),"system_state":state,
            "algorithm":algorithm
        }
        self.history.append(snap)
        return snap
