from fastapi.testclient import TestClient
from bromax.main import app

def test_health_is_read_only():
    with TestClient(app) as client:
        r=client.get("/api/health")
        assert r.status_code==200
        assert r.json()["trading_enabled"] is False
