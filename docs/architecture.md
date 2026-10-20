# RateGuard Architecture

Client -> Gateway -> Rate Limiter -> Mock Backend. Telemetry feeds an adaptive controller, which changes the configured rate within minimum/maximum bounds. WebSocket clients receive live snapshots.