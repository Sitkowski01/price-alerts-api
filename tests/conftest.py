import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ustawiamy srodowisko zanim zaimportujemy aplikacje — konfiguracja czyta je przy imporcie.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/price_alerts_test",
)
os.environ.setdefault("API_KEY", "klucz-testowy")
os.environ.setdefault("APP_ENV", "test")

from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

API_KEY = os.environ["API_KEY"]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def engine():
    silnik = create_async_engine(os.environ["DATABASE_URL"], future=True)
    async with silnik.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield silnik
    await silnik.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    """Czysta baza przed każdym testem — testy nie mogą się o siebie opierać."""
    fabryka = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with fabryka() as s:
        await s.execute(text("TRUNCATE triggers, alerts RESTART IDENTITY CASCADE"))
        await s.commit()
        yield s


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def podmien_sesje() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = podmien_sesje
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def naglowki() -> dict[str, str]:
    return {"X-API-Key": API_KEY}
