#!/bin/sh
# Resilient Docker startup: wait deps → schema → native → exec service command
set -e

SERVICE_ROLE="${SKYTRAX_SERVICE_ROLE:-app}"
echo "[BOOTSTRAP] SkyTrax entrypoint role=$SERVICE_ROLE"

# ── 1. Wait PostgreSQL ─────────────────────────────────────────────
if [ -n "$DATABASE_URL" ]; then
  echo "[BOOTSTRAP] Waiting for PostgreSQL..."
  python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text
url = os.environ.get("DATABASE_URL", "")
if not url:
    sys.exit(0)
for i in range(60):
    try:
        e = create_engine(url, pool_pre_ping=True)
        with e.connect() as c:
            c.execute(text("SELECT 1"))
        print("[BOOTSTRAP] PostgreSQL ready")
        sys.exit(0)
    except Exception as exc:
        if i == 59:
            print(f"[BOOTSTRAP] PostgreSQL timeout: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY
fi

# ── 2. Wait Redis ──────────────────────────────────────────────────
if [ -n "$REDIS_URL" ]; then
  echo "[BOOTSTRAP] Waiting for Redis..."
  python - <<'PY'
import os, sys, time
from redis import Redis
url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
for i in range(30):
    try:
        Redis.from_url(url).ping()
        print("[BOOTSTRAP] Redis ready")
        sys.exit(0)
    except Exception as exc:
        if i == 29:
            print(f"[BOOTSTRAP] Redis timeout: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY
fi

# ── 3. Startup governance (schema + native) ───────────────────────
echo "[BOOTSTRAP] Running startup governance..."
export SKYTRAX_STARTUP_BLOCK="${SCHEMA_BLOCK_ON_DRIFT:-false}"
python - <<PY
import os, sys
from database.session import engine
from app.startup_governance import run_startup_governance, log_startup_summary, StartupBlockedError

service = os.environ.get("SKYTRAX_SERVICE_ROLE", "app")
block = os.environ.get("SKYTRAX_STARTUP_BLOCK", "false").lower() in ("1", "true", "yes")
try:
    report = run_startup_governance(engine, service=service, block_on_failure=block)
    log_startup_summary(report)
except StartupBlockedError as exc:
    print(f"[SCHEMA] FATAL startup blocked: {exc}", file=sys.stderr)
    sys.exit(1)
PY

echo "[BOOTSTRAP] Startup complete — executing: $*"
exec "$@"
