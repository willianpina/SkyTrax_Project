from fastapi.testclient import TestClient

from api.main import app


def test_root_and_health_contracts() -> None:
    client = TestClient(app)
    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert root.json()["project"] == "SkyTrax Airline Intelligence Platform"
    assert health.status_code == 200
    assert health.json()["status"] == "online"


def test_openapi_contains_enterprise_routes() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/reputation" in paths
    assert "/api/benchmarking" in paths
    assert "/api/semantic-search" in paths
    assert "/api/forecasting" in paths
    assert "/api/forecasting/refresh" in paths
    assert "/api/anomalies" in paths
    assert "/api/anomalies/refresh" in paths
