from pydantic import BaseModel, Field
from typing import Literal

Algorithm = Literal["TOKEN_BUCKET", "LEAKY_BUCKET"]
SystemState = Literal["NORMAL", "WARNING", "HIGH_LOAD", "CRITICAL"]

class RateLimitConfig(BaseModel):
    algorithm: Algorithm = "TOKEN_BUCKET"
    min_rate: float = Field(5, gt=0)
    max_rate: float = Field(100, gt=0)
    current_rate: float = Field(50, gt=0)
    bucket_capacity: int = Field(50, gt=0)
    refill_rate: float = Field(50, gt=0)
    queue_capacity: int = Field(50, gt=0)
    leak_rate: float = Field(20, gt=0)

class RouteConfig(BaseModel):
    path: str
    backend_path: str
    rate_limit: float | None = None

class GatewayDecision(BaseModel):
    client: str
    route: str
    decision: Literal["ALLOW", "REJECT", "THROTTLE"]
    algorithm: Algorithm
    current_limit: float
    system_state: SystemState
    latency_ms: float
    reason: str
