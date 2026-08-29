import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import ApiKeyDep, SessionDep
from app.domain import AlertStatus, Direction, normalize_ticker
from app.models import Alert, Trigger
from app.schemas import AlertCreate, AlertPage, AlertRead, AlertUpdate, TriggerRead

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


async def _pobierz(session: SessionDep, alert_id: uuid.UUID) -> Alert:
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert nie istnieje")
    return alert


@router.post("", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
async def utworz(dane: AlertCreate, session: SessionDep, _: ApiKeyDep) -> Alert:
    alert = Alert(
        ticker=dane.ticker,
        direction=dane.direction,
        threshold=dane.threshold,
        note=dane.note,
        status=AlertStatus.ARMED,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


@router.get("", response_model=AlertPage)
async def lista(
    session: SessionDep,
    ticker: str | None = None,
    status_filter: Annotated[AlertStatus | None, Query(alias="status")] = None,
    direction: Direction | None = None,
    limit: Annotated[int, Query(ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AlertPage:
    limit = min(limit, get_settings().max_page_size)

    warunki = []
    if ticker:
        # Ta sama normalizacja co przy zapisie — inaczej filtr rozjedzie sie
        # z tym, co faktycznie stoi w bazie, gdy regula normalizacji sie zmieni.
        warunki.append(Alert.ticker == normalize_ticker(ticker))
    if status_filter:
        warunki.append(Alert.status == status_filter)
    if direction:
        warunki.append(Alert.direction == direction)

    total = await session.scalar(select(func.count()).select_from(Alert).where(*warunki))
    wynik = await session.scalars(
        # Drugie kryterium porzadku jest konieczne: dwa alerty z tym samym
        # created_at ustawialyby sie losowo, wiec przy stronicowaniu jeden
        # potrafil pojawic sie dwa razy, a inny w ogole nie wyjsc.
        select(Alert)
        .where(*warunki)
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return AlertPage(
        total=total or 0,
        limit=limit,
        offset=offset,
        items=[AlertRead.model_validate(a) for a in wynik],
    )


@router.get("/{alert_id}", response_model=AlertRead)
async def szczegoly(alert_id: uuid.UUID, session: SessionDep) -> Alert:
    return await _pobierz(session, alert_id)


@router.patch("/{alert_id}", response_model=AlertRead)
async def zmien(alert_id: uuid.UUID, dane: AlertUpdate, session: SessionDep, _: ApiKeyDep) -> Alert:
    alert = await _pobierz(session, alert_id)

    zmiany = dane.model_dump(exclude_unset=True)
    for pole, wartosc in zmiany.items():
        setattr(alert, pole, wartosc)

    await session.commit()
    await session.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def usun(alert_id: uuid.UUID, session: SessionDep, _: ApiKeyDep) -> None:
    alert = await _pobierz(session, alert_id)
    await session.delete(alert)
    await session.commit()


@router.get("/{alert_id}/triggers", response_model=list[TriggerRead])
async def historia(
    alert_id: uuid.UUID,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1)] = 50,
) -> list[Trigger]:
    await _pobierz(session, alert_id)
    limit = min(limit, get_settings().max_page_size)

    wynik = await session.scalars(
        select(Trigger)
        .where(Trigger.alert_id == alert_id)
        .order_by(Trigger.created_at.desc(), Trigger.id.desc())
        .limit(limit)
    )
    return list(wynik)
