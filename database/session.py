from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base shared by API, Scrapy pipelines and workers."""


settings = get_settings()
_engine_generation = 0


def _engine_connect_args(url: str) -> dict:
    """SQLite cannot use PostgreSQL pool settings."""
    if url.startswith("sqlite"):
        return {"future": True}
    return {
        "pool_pre_ping": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "future": True,
    }


def _driver_connect_args(url: str) -> dict:
    """psycopg3: disable server-side prepared statements after DDL (DuplicatePreparedStatement)."""
    if "psycopg" not in url:
        return {}
    return {"prepare_threshold": None}


def _build_engine(url: str | None = None):
    url = url or settings.database_url
    return create_engine(
        url,
        connect_args=_driver_connect_args(url),
        **_engine_connect_args(url),
    )


engine = _build_engine()
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
)


def engine_generation() -> int:
    return _engine_generation


def dispose_sqlalchemy_runtime(*, reason: str = "unspecified") -> dict:
    """Dispose pooled connections and recreate the module-level engine + sessionmaker."""
    global engine, SessionLocal, _engine_generation

    logger.warning("[ENGINE_DISPOSE] Disposing engine reason=%s gen=%s", reason, _engine_generation)
    try:
        engine.dispose()
    except Exception as exc:
        logger.warning("[ENGINE_DISPOSE] dispose failed: %s", exc)

    _engine_generation += 1
    engine = _build_engine()
    SessionLocal.configure(bind=engine)

    return {
        "engine_generation": _engine_generation,
        "reason": reason,
        "engine": engine,
    }


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
