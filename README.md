# RateGuard

Adaptive API Gateway & Dynamic Rate Limiting Engine.

RateGuard sits between clients and backend services and dynamically adjusts request limits using live telemetry.

## Stack
- Python 3.12+
- FastAPI + Uvicorn
- SQLite for prototype history/config
- WebSockets for live metrics
- React + Vite
- Recharts
- Docker Compose

## Quick start

### Local
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal:
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Docker
```bash
docker compose up --build
```
Open http://localhost:5173

## Demo flow

1. Open the dashboard.
2. Send traffic through `POST /api/orders` or `GET /api/products`.
3. Use `python load_test/load_test.py --url http://localhost:8000/api/products --rps 30 --duration 20`.
4. Watch Requests/sec, latency, CPU/memory, queue length and dynamic rate change.
5. Switch Token Bucket / Leaky Bucket with `PUT /rate-limit/config`.
6. Stop the load and observe gradual recovery.

## Main APIs

- `GET /health`
- `GET /metrics`
- `GET /metrics/history`
- `GET /rate-limit/status`
- `GET /rate-limit/config`
- `PUT /rate-limit/config`
- `GET /clients`
- `GET /routes`
- `POST /routes`
- `DELETE /routes/{route_id}`
- `GET /system/status`
- `GET /gateway/stats`
- `WS /ws/metrics`

FastAPI OpenAPI docs: http://localhost:8000/docs

## Architecture

Client -> RateGuard Gateway -> Adaptive Controller -> Rate Limiter -> Mock Backend

The adaptive controller uses smoothed CPU, memory, queue, latency, throughput and error telemetry to select NORMAL, WARNING, HIGH_LOAD or CRITICAL and adjusts the rate between configured minimum and maximum bounds.

## Limitations
This prototype keeps rate-limiter state in process memory and uses SQLite. A production deployment should use Redis for distributed state, a durable metrics store, authentication/authorization for administrative APIs, and multiple gateway workers with shared coordination.
