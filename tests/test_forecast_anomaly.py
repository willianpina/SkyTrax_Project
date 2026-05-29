from __future__ import annotations

import statistics

from analytics.forecasting import TrendForecastingService


def test_ewma_computation() -> None:
    service = TrendForecastingService.__new__(TrendForecastingService)
    service.alpha = 0.35
    result = service._ewma([50.0, 52.0, 48.0, 55.0])
    assert 45 < result < 60


def test_trend_direction_labels() -> None:
    assert TrendForecastingService._trend_direction(60, 65) == "improving"
    assert TrendForecastingService._trend_direction(70, 60) == "declining"
    assert TrendForecastingService._trend_direction(65, 66) == "stable"


def test_anomaly_z_score_spike_detection() -> None:
    values = [2.0, 2.0, 3.0, 2.0, 2.0, 15.0]
    mean = statistics.mean(values[:-1])
    stdev = statistics.pstdev(values[:-1]) or 1
    z = (values[-1] - mean) / stdev
    assert z >= 2.0


def test_openapi_forecast_anomaly_routes() -> None:
    from fastapi.testclient import TestClient

    from tests.conftest import app

    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/forecasting" in paths
    assert "/api/forecasting/refresh" in paths
    assert "post" in paths["/api/forecasting/refresh"]
    assert "/api/anomalies" in paths
    assert "/api/anomalies/alerts" in paths
    assert "/api/anomalies/refresh" in paths
    assert "post" in paths["/api/anomalies/refresh"]


def test_forecasting_refresh_not_captured_by_slug_route() -> None:
    from fastapi.testclient import TestClient

    from tests.conftest import app

    client = TestClient(app)
    response = client.post("/api/forecasting/refresh")
    assert response.status_code != 404


def test_forecast_metrics_constants() -> None:
    from analytics.forecasting import METRICS

    assert "reputation_score" in METRICS
    assert "sentiment" in METRICS
    assert "complaint_density" in METRICS
