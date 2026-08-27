import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Srodowisko ustawiamy przed importem aplikacji — konfiguracja czyta je przy imporcie.
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
DATABASE_URL = os.environ["DATABASE_URL"]


# Schemat zakladamy raz, przy pierwszym tescie, ktory faktycznie prosi o baze.
# Nie przy imporcie modulu — inaczej testy domenowe, ktore bazy nie potrzebuja,
# nie daloby sie uruchomic bez postawionego Postgresa.
_schemat_gotowy = False


@pytest.fixture
async def engine() -> AsyncIterator:
    """Silnik na każdy test osobno.

    Silnik nie może żyć dłużej niż pętla zdarzeń, w której powstał — połączenie
    asyncpg jest z nią związane, a pytest-asyncio daje każdemu testowi własną pętlę.
    """
    global _schemat_gotowy

    silnik = create_async_engine(DATABASE_URL, poolclass=NullPool)

    if not _schemat_gotowy:
        async with silnik.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        _schemat_gotowy = True

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
