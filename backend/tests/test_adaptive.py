from app.adaptive import AdaptiveController, Telemetry, State

def test_normal_stays_bounded():
    c=AdaptiveController(5,100,50,cooldown=0)
    rate,state=c.update(Telemetry(cpu=20,memory=20,latency_ms=10))
    assert state==State.NORMAL
    assert 5 <= rate <= 100

def test_critical_reduces():
    c=AdaptiveController(5,100,50,cooldown=0)
    rate,state=c.update(Telemetry(cpu=99,memory=99,latency_ms=2000,error_rate=30))
    assert state==State.CRITICAL
    assert rate < 50
