"""Native dependency probe — isolated from analytics/forecasting to avoid DB engine import."""

from __future__ import annotations

import logging
import os
import platform
import struct
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


def _architecture_info() -> dict[str, str]:
    machine = platform.machine().lower()
    is_arm = machine in ("arm64", "aarch64")
    bits = struct.calcsize("P") * 8
    return {
        "platform": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "bits": str(bits),
        "architecture": "arm64" if is_arm else ("x86_64" if bits == 64 else "x86"),
        "apple_silicon": str(platform.system() == "Darwin" and is_arm).lower(),
    }


def _exit_signal(returncode: int | None) -> int | None:
    if returncode is None:
        return None
    if returncode < 0:
        return -returncode
    if returncode > 128:
        return returncode - 128
    return None


def _safe_import_probe(module_name: str) -> dict[str, Any]:
    code = f"import {module_name}; v = getattr({module_name}, '__version__', 'unknown'); print(v)"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "")[-500:]
            signal = _exit_signal(proc.returncode)
            if signal == 11:
                logger.error("[SEGFAULT] Import probe segfault module=%s", module_name)
            return {
                "available": False,
                "version": None,
                "error": stderr or f"exit={proc.returncode}",
                "signal": signal,
                "segfault": signal == 11,
            }
        return {
            "available": True,
            "version": (proc.stdout or "").strip() or "unknown",
            "error": None,
            "signal": None,
            "segfault": False,
        }
    except subprocess.TimeoutExpired:
        return {"available": False, "version": None, "error": "timeout", "signal": None, "segfault": False}
    except Exception as exc:
        return {"available": False, "version": None, "error": str(exc), "signal": None, "segfault": False}


def probe_numpy_operation() -> dict[str, Any]:
    code = "import numpy as np; a=np.array([1.0,2.0,3.0]); print(float(a.mean()))"
    return _run_probe_script("numpy_mean", code)


def probe_scipy_operation() -> dict[str, Any]:
    code = "import scipy; print(scipy.__version__)"
    return _run_probe_script("scipy", code)


def probe_pandas_rolling() -> dict[str, Any]:
    code = "import pandas as pd; s=pd.Series([1.0,2.0,3.0,4.0]); print(float(s.rolling(2).mean().iloc[-1]))"
    return _run_probe_script("pandas_rolling", code)


def probe_sklearn_import() -> dict[str, Any]:
    return _safe_import_probe("sklearn")


def probe_sentence_transformers_import() -> dict[str, Any]:
    return _safe_import_probe("sentence_transformers")


def _run_probe_script(name: str, code: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        )
        signal = _exit_signal(proc.returncode)
        if signal == 11:
            logger.error("[SEGFAULT] Native probe segfault name=%s", name)
        ok = proc.returncode == 0
        return {
            "name": name,
            "ok": ok,
            "output": (proc.stdout or "").strip()[:100],
            "error": (proc.stderr or "")[-300:] if not ok else None,
            "signal": signal,
            "segfault": signal == 11,
        }
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "error": "timeout", "segfault": False}
    except Exception as exc:
        return {"name": name, "ok": False, "error": str(exc), "segfault": False}


def collect_native_health() -> dict[str, Any]:
    """Full native stack report for /ops/health/native."""
    arch = _architecture_info()
    probes = {
        "numpy": _safe_import_probe("numpy"),
        "scipy": _safe_import_probe("scipy"),
        "pandas": _safe_import_probe("pandas"),
        "sklearn": probe_sklearn_import(),
        "sentence_transformers": probe_sentence_transformers_import(),
        "spacy": _safe_import_probe("spacy"),
    }

    blas_backend = "unknown"
    if probes["numpy"].get("available"):
        try:
            proc = subprocess.run(
                [sys.executable, "-c", "import numpy as np; np.show_config()"],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "OMP_NUM_THREADS": "1"},
            )
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines():
                    if "blas" in line.lower() or "openblas" in line.lower():
                        blas_backend = line.strip()[:120]
                        break
        except Exception:
            pass

    smoke = {
        "numpy_mean": probe_numpy_operation(),
        "scipy": probe_scipy_operation(),
        "pandas_rolling": probe_pandas_rolling(),
        "sklearn_import": probe_sklearn_import(),
        "sentence_transformers_import": probe_sentence_transformers_import(),
    }

    any_segfault = any(p.get("segfault") for p in probes.values()) or any(
        s.get("segfault") for s in smoke.values()
    )

    return {
        **arch,
        "numpy_version": probes["numpy"].get("version"),
        "scipy_version": probes["scipy"].get("version"),
        "pandas_version": probes["pandas"].get("version"),
        "sklearn_version": probes["sklearn"].get("version"),
        "blas_backend": blas_backend,
        "dependencies": probes,
        "smoke_tests": smoke,
        "any_segfault_detected": any_segfault,
        "forecast_safe_mode_recommended": any_segfault or arch["apple_silicon"] == "true",
    }
