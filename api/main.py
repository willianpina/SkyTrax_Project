from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

from api.routes import router
from api.routers.anomalies import router as anomalies_router
from api.routers.forecasting import router as forecasting_router
from api.schemas import ServiceStatusResponse
from app.config import get_settings
from app.logging_config import configure_logging
from app.observability import instrument_sqlalchemy, prometheus_response
from app.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TimeoutMiddleware,
)
from app.tracing import configure_tracing
from sqlalchemy.orm import Session

from database.session import get_session, engine


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
instrument_sqlalchemy(engine)
configure_tracing("skytrax-api")

app = FastAPI(
    title="Airline Review Intelligence API",
    version="0.2.0",
    description="Customer experience, marketing intelligence and reputation analytics for airline reviews.",
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host.strip() for host in settings.api_trusted_hosts.split(",")])
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.api_max_request_bytes)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.api_rate_limit_per_minute)
app.add_middleware(TimeoutMiddleware, timeout_seconds=settings.api_request_timeout_seconds)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.api_cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(forecasting_router, prefix="/api")
app.include_router(anomalies_router, prefix="/api")


@app.get("/", response_model=ServiceStatusResponse)
def root() -> ServiceStatusResponse:
    return {
        "project": "SkyTrax Airline Intelligence Platform",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", response_model=ServiceStatusResponse)
def health() -> ServiceStatusResponse:
    return {
        "project": "SkyTrax Airline Intelligence Platform",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(session: Session = Depends(get_session)):
    return prometheus_response(session)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("database_error", extra={"service": "api", "path": str(request.url.path)})
    return JSONResponse(status_code=503, content={"detail": "Database service is temporarily unavailable."})


@app.exception_handler(NoResultFound)
async def not_found_exception_handler(request, exc: NoResultFound) -> JSONResponse:
    logger.info("resource_not_found", extra={"service": "api", "path": str(request.url.path)})
    return JSONResponse(status_code=404, content={"detail": "Resource not found."})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("request_validation_error", extra={"service": "api", "path": str(request.url.path)})
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError) -> JSONResponse:
    logger.warning("response_validation_error", extra={"service": "api", "path": str(request.url.path)})
    return JSONResponse(status_code=500, content={"detail": "Response validation failed."})


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_api_error", extra={"service": "api", "path": str(request.url.path)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
