from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from os import getenv


def _env_or_file(name: str, default: str) -> str:
    file_path = getenv(f"{name}_FILE")
    if file_path:
        try:
            with open(file_path, encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return default
    return getenv(name, default)


@dataclass(frozen=True)
class Settings:
    """Centralized runtime configuration loaded from environment variables."""

    environment: str = getenv("APP_ENV", "development")
    log_level: str = getenv("LOG_LEVEL", "INFO")
    database_url: str = _env_or_file(
        "DATABASE_URL",
        "postgresql+psycopg://skytrax:skytrax@localhost:5432/skytrax",
    )
    redis_url: str = _env_or_file("REDIS_URL", "redis://localhost:6379/0")
    api_cors_origins: str = getenv("API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    api_trusted_hosts: str = getenv("API_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver,app,0.0.0.0")
    api_rate_limit_per_minute: int = int(getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
    api_max_request_bytes: int = int(getenv("API_MAX_REQUEST_BYTES", "1048576"))
    api_request_timeout_seconds: float = float(getenv("API_REQUEST_TIMEOUT_SECONDS", "30"))
    scrape_user_agent: str = getenv(
        "SCRAPE_USER_AGENT",
        "SkyTraxAnalyticsBot/0.1 (+contact: analytics@example.com)",
    )
    scrape_rate_limit_seconds: float = float(getenv("SCRAPE_RATE_LIMIT_SECONDS", "2.0"))
    scrape_timeout_seconds: int = int(getenv("SCRAPE_TIMEOUT_SECONDS", "20"))
    max_retries: int = int(getenv("MAX_RETRIES", "3"))
    embedding_dimension: int = int(getenv("EMBEDDING_DIMENSION", "384"))
    nlp_enable_embeddings: bool = getenv("NLP_ENABLE_EMBEDDINGS", "false").lower() == "true"
    nlp_embedding_model: str = getenv("NLP_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    database_pool_size: int = int(getenv("DATABASE_POOL_SIZE", "10"))
    database_max_overflow: int = int(getenv("DATABASE_MAX_OVERFLOW", "10"))
    database_pool_timeout: int = int(getenv("DATABASE_POOL_TIMEOUT", "30"))
    scheduler_enabled: bool = getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    scheduler_timezone: str = getenv("SCHEDULER_TIMEZONE", "UTC")
    crawl_interval_hours: int = int(getenv("CRAWL_INTERVAL_HOURS", "6"))
    crawl_max_pages: int = int(getenv("CRAWL_MAX_PAGES", "5"))
    crawl_deep_max_pages: int = int(getenv("CRAWL_DEEP_MAX_PAGES", "0"))
    crawl_skip_recent_hours: int = int(getenv("CRAWL_SKIP_RECENT_HOURS", "0"))
    nlp_interval_minutes: int = int(getenv("NLP_INTERVAL_MINUTES", "30"))
    snapshot_hourly_minutes: int = int(getenv("SNAPSHOT_HOURLY_MINUTES", "60"))
    snapshot_daily_hour: int = int(getenv("SNAPSHOT_DAILY_HOUR", "2"))
    insights_interval_hours: int = int(getenv("INSIGHTS_INTERVAL_HOURS", "4"))
    cleanup_interval_hours: int = int(getenv("CLEANUP_INTERVAL_HOURS", "24"))
    semantic_similarity_threshold: float = float(getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.12"))
    job_retry_attempts: int = int(getenv("JOB_RETRY_ATTEMPTS", "3"))
    job_overlap_lock_minutes: int = int(getenv("JOB_OVERLAP_LOCK_MINUTES", "120"))
    alert_webhook_url: str | None = getenv("ALERT_WEBHOOK_URL") or None
    forecast_interval_hours: int = int(getenv("FORECAST_INTERVAL_HOURS", "4"))
    anomaly_interval_hours: int = int(getenv("ANOMALY_INTERVAL_HOURS", "2"))
    priority_airlines: str = getenv(
        "PRIORITY_AIRLINES",
        "british-airways,emirates,qatar-airways,lufthansa,latam-airlines",
    )
    enable_postgis: bool = getenv("ENABLE_POSTGIS", "false").lower() in {"true", "1", "yes", "on"}
    schema_validate_on_startup: bool = getenv("SCHEMA_VALIDATE_ON_STARTUP", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    schema_auto_migrate_dev: bool = getenv("SCHEMA_AUTO_MIGRATE_DEV", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    schema_auto_migrate_staging: bool = getenv("SCHEMA_AUTO_MIGRATE_STAGING", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    schema_block_on_drift: bool = getenv("SCHEMA_BLOCK_ON_DRIFT", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    aviation_schema_auto_repair: bool = getenv("AVIATION_SCHEMA_AUTO_REPAIR", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    aviation_schema_block_on_drift: bool = getenv("AVIATION_SCHEMA_BLOCK_ON_DRIFT", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    alembic_version_auto_repair: bool = getenv("ALEMBIC_VERSION_AUTO_REPAIR", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    alembic_version_min_length: int = int(getenv("ALEMBIC_VERSION_MIN_LENGTH", "128"))
    alembic_block_on_truncation_risk: bool = getenv(
        "ALEMBIC_BLOCK_ON_TRUNCATION_RISK",
        "false",
    ).lower() in {"true", "1", "yes", "on"}
    startup_native_probe: bool = getenv("STARTUP_NATIVE_PROBE", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    forecast_safe_mode: bool = getenv("FORECAST_SAFE_MODE", "0").lower() in {"true", "1", "yes", "on"}
    forecast_isolated: bool = getenv("FORECAST_ISOLATED", "1").lower() in {"true", "1", "yes", "on"}
    forecast_auto_safe_mode: bool = getenv("FORECAST_AUTO_SAFE_MODE", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
