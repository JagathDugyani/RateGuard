# Adaptive Control

Telemetry is smoothed with an exponential moving average. Thresholds classify NORMAL, WARNING, HIGH_LOAD and CRITICAL. Cooldown prevents rapid oscillation; rate changes are bounded.