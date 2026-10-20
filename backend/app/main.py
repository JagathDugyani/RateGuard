
import asyncio
import time
import logging
import httpx

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .models import RateLimitConfig, RouteConfig
from .rate_limiter import RateLimiterManager
from .adaptive import AdaptiveController, Telemetry
from .telemetry import TelemetryService
from .db import init_db, save_metric, history


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("rateguard")


# -------------------- Configuration --------------------

config = RateLimitConfig(
    min_rate=settings.min_rate,
    max_rate=settings.max_rate,
    current_rate=settings.initial_rate,
    bucket_capacity=settings.bucket_capacity,
    refill_rate=settings.refill_rate,
    queue_capacity=settings.queue_capacity,
    leak_rate=settings.leak_rate,
)

limiter = RateLimiterManager(config)

controller = AdaptiveController(
    config.min_rate,
    config.max_rate,
    config.current_rate,
    settings.cooldown_seconds,
)

telemetry = TelemetryService(settings.telemetry_interval)

clients = {}

routes = {
    "/api/users": "/users",
    "/api/products": "/products",
    "/api/orders": "/orders",
}

subscribers = set()


# -------------------- Application Lifecycle --------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Reuse one HTTP client and its connection pool.
    async with httpx.AsyncClient(timeout=10.0) as client:
        app.state.http_client = client

        task = asyncio.create_task(telemetry_loop())

        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="RateGuard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        x.strip() for x in settings.cors_origins.split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- Telemetry Loop --------------------

async def telemetry_loop():
    while True:
        snap = telemetry.snapshot(
            config.current_rate,
            state=controller.state.value,
            algorithm=limiter.algorithm,
        )

        t = Telemetry(
            cpu=snap["cpu_utilization"],
            memory=snap["memory_utilization"],
            queue=snap["queue_length"],
            latency_ms=snap["avg_latency_ms"],
            throughput=snap["requests_per_sec"],
            active=snap["active_requests"],
        )

        rate, state = controller.update(t)
        config.current_rate = rate

        # Apply the adaptive rate to the active limiter.
        if limiter.algorithm == "TOKEN_BUCKET":
            limiter.limiter.refill_rate = rate
            limiter.limiter.capacity = max(
                1, int(config.bucket_capacity)
            )
        else:
            limiter.limiter.leak_rate = rate
            limiter.limiter.capacity = max(
                1, int(config.queue_capacity)
            )

        snap["current_rate_limit"] = round(rate, 2)
        snap["system_state"] = state.value

        save_metric(snap)

        dead = []

        for ws in list(subscribers):
            try:
                await ws.send_json(snap)
            except Exception:
                dead.append(ws)

        for ws in dead:
            subscribers.discard(ws)

        await asyncio.sleep(settings.telemetry_interval)


# -------------------- Health & Metrics --------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "rateguard"}


@app.get("/metrics")
async def metrics():
    return telemetry.snapshot(
        config.current_rate,
        state=controller.state.value,
        algorithm=limiter.algorithm,
    )


@app.get("/metrics/history")
async def metrics_history():
    return history()


@app.get("/rate-limit/status")
async def rate_status():
    return {
        **config.model_dump(),
        "system_state": controller.state.value,
        "utilization": limiter.utilization("global"),
    }


@app.get("/rate-limit/config")
async def get_config():
    return config


@app.put("/rate-limit/config")
async def put_config(new: RateLimitConfig):
    global config, limiter, controller

    config = new
    limiter.config = config
    limiter.switch(config.algorithm)

    controller.min_rate = config.min_rate
    controller.max_rate = config.max_rate
    controller.rate = config.current_rate

    return config


@app.get("/clients")
async def get_clients():
    return list(clients.values())


@app.get("/routes")
async def get_routes():
    return [
        {"path": k, "backend_path": v}
        for k, v in routes.items()
    ]


@app.post("/routes")
async def add_route(route: RouteConfig):
    routes[route.path] = route.backend_path
    return route


@app.delete("/routes/{route_id:path}")
async def delete_route(route_id: str):
    path = "/" + route_id if not route_id.startswith("/") else route_id

    if path not in routes:
        raise HTTPException(404, "Route not found")

    del routes[path]
    return {"deleted": path}


@app.get("/system/status")
async def system_status():
    return {
        "state": controller.state.value,
        "rate_limit": config.current_rate,
    }


@app.get("/gateway/stats")
async def gateway_stats():
    return {
        "total": telemetry.total,
        "accepted": telemetry.accepted,
        "rejected": telemetry.rejected,
        "avg_latency_ms": round(
            sum(telemetry.latencies) / len(telemetry.latencies), 2
        ) if telemetry.latencies else 0,
    }


# -------------------- WebSocket --------------------

@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    await ws.accept()
    subscribers.add(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        subscribers.discard(ws)
    except Exception:
        subscribers.discard(ws)


# -------------------- Gateway Proxy --------------------

async def proxy(request: Request, path: str):
    client_id = (
        request.headers.get("x-api-key")
        or (request.client.host if request.client else "unknown")
    )

    start = time.perf_counter()

    clients.setdefault(
        client_id,
        {
            "client": client_id,
            "requests": 0,
            "accepted": 0,
            "rejected": 0,
            "current_limit": config.current_rate,
            "usage_percentage": 0,
        },
    )

    clients[client_id]["requests"] += 1

    # Diagnostic timing: entry and limiter decision.
    log.info("PROXY ENTER route=%s client=%s", path, client_id)

    limiter_start = time.perf_counter()
    allowed = await limiter.allow(client_id)
    limiter_ms = (time.perf_counter() - limiter_start) * 1000

    log.info(
        "LIMITER DONE route=%s allowed=%s elapsed_ms=%.2f",
        path,
        allowed,
        limiter_ms,
    )

    if not allowed:
        latency = (time.perf_counter() - start) * 1000

        telemetry.record(False, latency, 429)
        clients[client_id]["rejected"] += 1
        clients[client_id]["current_limit"] = config.current_rate

        log.info(
            "GATEWAY REJECT route=%s algorithm=%s limit=%.2f state=%s",
            path,
            limiter.algorithm,
            config.current_rate,
            controller.state.value,
        )

        raise HTTPException(429, "Rate limit exceeded")

    target = settings.backend_url + routes.get(path, path)

    query = "&".join(
        f"{k}={v}"
        for k, v in request.query_params.multi_items()
    )

    if query:
        target += "?" + query

    body = await request.body()

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "connection"}
    }

    telemetry.active += 1

    try:
        # Reuse the HTTP client created during application startup.
        client = request.app.state.http_client

        backend_start = time.perf_counter()

        r = await client.request(
            request.method,
            target,
            headers=headers,
            content=body,
        )

        backend_ms = (time.perf_counter() - backend_start) * 1000
        latency = (time.perf_counter() - start) * 1000

        telemetry.record(True, latency, r.status_code)

        clients[client_id]["accepted"] += 1
        clients[client_id]["current_limit"] = config.current_rate

        log.info(
            "PROXY DONE route=%s status=%s limiter_ms=%.2f "
            "backend_ms=%.2f total_ms=%.2f",
            path,
            r.status_code,
            limiter_ms,
            backend_ms,
            latency,
        )

        # Avoid forwarding hop-by-hop or stale body-length headers.
        excluded_headers = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailer",
            "transfer-encoding",
            "upgrade",
            "content-length",
            "content-encoding",
        }

        response_headers = {
            k: v
            for k, v in r.headers.items()
            if k.lower() not in excluded_headers
        }

        return Response(
            content=r.content,
            status_code=r.status_code,
            headers=response_headers,
        )

    except httpx.TimeoutException as e:
        latency = (time.perf_counter() - start) * 1000
        telemetry.record(True, latency, 502)

        log.exception("BACKEND TIMEOUT route=%s", path)

        raise HTTPException(
            502,
            "Backend request timed out",
        ) from e

    except httpx.HTTPError as e:
        latency = (time.perf_counter() - start) * 1000
        telemetry.record(True, latency, 502)

        log.exception("BACKEND HTTP ERROR route=%s", path)

        raise HTTPException(
            502,
            "Backend connection failed",
        ) from e

    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        telemetry.record(True, latency, 502)

        log.exception("PROXY ERROR route=%s", path)

        raise HTTPException(
            502,
            f"Gateway proxy error: {type(e).__name__}",
        ) from e

    finally:
        telemetry.active = max(0, telemetry.active - 1)


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def gateway(request: Request, path: str):
    full_path = "/api/" + path
    return await proxy(request, full_path)


# -------------------- Mock Backend --------------------
# These endpoints intentionally live in the same service.

@app.get("/users")
async def users(delay: int = 0):
    if delay:
        await asyncio.sleep(min(delay, 5000) / 1000)

    return {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
    }


@app.get("/products")
async def products(delay: int = 0):
    if delay:
        await asyncio.sleep(min(delay, 5000) / 1000)

    return {
        "products": [
            {"id": 1, "name": "RateGuard API"},
            {"id": 2, "name": "Adaptive Service"},
        ]
    }


@app.post("/orders")
async def orders(delay: int = 0):
    if delay:
        await asyncio.sleep(min(delay, 5000) / 1000)

    return {
        "order_id": f"ORD-{int(time.time() * 1000)}",
        "status": "created",
    }
