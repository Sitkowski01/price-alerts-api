import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import get_settings
from app.db import dispose_engine
from app.logging_config import setup_logging
from app.routers import alerts, health, quotes

logger = logging.getLogger("price_alerts")

ZAPYTANIA = Counter("http_requests_total", "Liczba zapytań HTTP", ["method", "path", "status"])
CZAS = Histogram("http_request_duration_seconds", "Czas obsługi zapytania", ["method", "path"])


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(get_settings().log_level)
    logger.info("Start serwisu alertów cenowych")
    yield
    await dispose_engine()
    logger.info("Serwis zatrzymany")


app = FastAPI(
    title="Price Alerts API",
    description="Alerty cenowe: reguły progowe i ocena napływających notowań.",
    version="0.1.0",
    lifespan=lifespan,
)


# Klient webowy (price-alerts-web) chodzi po przegladarce, wiec bez tego
# kazde zapytanie konczy sie odmowa jeszcze przed wyslaniem.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def obserwowalnosc(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()

    response = await call_next(request)

    trwalo = time.perf_counter() - start
    # Etykietujemy wzorcem trasy, nie adresem — inaczej kazde UUID
    # tworzyloby osobna serie czasowa w Prometheusie.
    wzorzec = request.scope.get("route").path if request.scope.get("route") else "unknown"

    ZAPYTANIA.labels(request.method, wzorzec, response.status_code).inc()
    CZAS.labels(request.method, wzorzec).observe(trwalo)

    response.headers["X-Request-ID"] = request_id
    logger.info(
        "zapytanie obsłużone",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(trwalo * 1000, 2),
            "request_id": request_id,
        },
    )
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(health.router)
app.include_router(alerts.router)
app.include_router(quotes.router)
