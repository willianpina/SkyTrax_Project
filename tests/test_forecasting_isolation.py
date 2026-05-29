"""Tests for forecasting isolation and safe mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from worker.forecasting_isolation import (
    _exit_signal,
    _fallback_safe,
    run_forecasting_isolated,
)


def test_exit_signal_negative():
    assert _exit_signal(-11) == 11


def test_exit_signal_sigterm():
    assert _exit_signal(-15) == 15


def test_exit_signal_normal():
    assert _exit_signal(0) is None


def test_safe_mode_linear_trend_pure_python():
    """Mirror SafeTrendForecastingService._linear_trend (stdlib only)."""
    values = [1.0, 2.0, 3.0, 4.0]
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((x - mean_x) ** 2 for x in xs) or 1.0
    assert num / den > 0


def test_run_forecasting_safe_mode_inprocess():
    mock_result = {"forecasts_persisted": 3, "mode": "safe"}
    with patch("worker.forecasting_isolation._run_forecasting_inprocess", return_value=mock_result):
        with patch.dict("os.environ", {"FORECAST_SAFE_MODE": "1", "FORECAST_ISOLATED": "0"}):
            result = run_forecasting_isolated()
    assert result["forecasts_persisted"] == 3


def test_fallback_safe_on_native_crash():
    mock_result = {"forecasts_persisted": 2, "mode": "safe"}
    with patch("worker.forecasting_isolation._run_forecasting_inprocess", return_value=mock_result):
        result = _fallback_safe("segfault_signal_11", heartbeat_fn=None, native_crash=True)
    assert result["forecasts_persisted"] == 2
    assert result["native_crash"] is True
    assert result["fallback_reason"] == "segfault_signal_11"


def test_isolated_subprocess_success():
    payload = {"status": "ok", "result": {"forecasts_persisted": 5, "mode": "full"}}
    mock_proc = MagicMock()
    mock_proc.is_alive.return_value = False
    mock_proc.exitcode = 0

    mock_queue = MagicMock()
    mock_queue.get_nowait.return_value = payload

    mock_ctx = MagicMock()
    mock_ctx.Queue.return_value = mock_queue
    mock_ctx.Process.return_value = mock_proc

    with patch("worker.forecasting_isolation.multiprocessing.get_context", return_value=mock_ctx):
        with patch.dict("os.environ", {"FORECAST_ISOLATED": "1", "FORECAST_SAFE_MODE": "0"}):
            result = run_forecasting_isolated()
    assert result["forecasts_persisted"] == 5
    assert result.get("isolation") == "subprocess"


def test_isolated_subprocess_segfault_triggers_fallback():
    mock_proc = MagicMock()
    mock_proc.is_alive.return_value = False
    mock_proc.exitcode = -11

    mock_queue = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.Queue.return_value = mock_queue
    mock_ctx.Process.return_value = mock_proc

    fallback_result = {"forecasts_persisted": 1, "mode": "safe"}

    with patch("worker.forecasting_isolation.multiprocessing.get_context", return_value=mock_ctx):
        with patch("worker.forecasting_isolation._fallback_safe", return_value=fallback_result) as mock_fb:
            with patch.dict("os.environ", {"FORECAST_ISOLATED": "1"}):
                result = run_forecasting_isolated()
    mock_fb.assert_called_once()
    assert mock_fb.call_args.kwargs.get("native_crash") is True
    assert result["forecasts_persisted"] == 1


def test_native_probe_architecture():
    from app.native_health import _architecture_info

    info = _architecture_info()
    assert "architecture" in info
    assert "python_version" in info
    assert "apple_silicon" in info
