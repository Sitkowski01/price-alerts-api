from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.deps import ApiKeyDep, SessionDep
from app.domain import AlertRule, AlertStatus, should_trigger
from app.models import Alert, Trigger
from app.schemas import AlertRead, QuoteIn, QuoteResult

router = APIRouter(prefix="/v1/quotes", tags=["quotes"])


@router.post("", response_model=QuoteResult)
async def przyjmij_notowanie(quote: QuoteIn, session: SessionDep, _: ApiKeyDep) -> QuoteResult:
    """Ocenia napływające notowanie względem uzbrojonych alertów na ten instrument.

    Alerty blokujemy na czas transakcji (`FOR UPDATE`), bo dwa notowania tego samego
    instrumentu obsługiwane równolegle inaczej uruchomiłyby ten sam alert dwa razy.
    """
    kandydaci = list(
        await session.scalars(
            select(Alert)
            .where(Alert.ticker == quote.ticker, Alert.status == AlertStatus.ARMED)
            .with_for_update()
        )
    )

    uruchomione: list[Alert] = []

    for alert in kandydaci:
        regula = AlertRule(
            ticker=alert.ticker,
            direction=alert.direction,
            threshold=alert.threshold,
            status=alert.status,
        )
        if not should_trigger(regula, quote.price):
            continue

        # Powtorka tego samego notowania (retry, replay z kolejki) nie tworzy
        # drugiego wpisu — decyduje o tym unikalny indeks (alert_id, quote_ts).
        wstawiony = await session.scalar(
            pg_insert(Trigger)
            .values(alert_id=alert.id, price=quote.price, quote_ts=quote.quote_ts)
            .on_conflict_do_nothing(constraint="uq_triggers_alert_quote_ts")
            .returning(Trigger.id)
        )
        if wstawiony is None:
            continue

        alert.status = AlertStatus.TRIGGERED
        uruchomione.append(alert)

    await session.commit()
    for alert in uruchomione:
        await session.refresh(alert)

    return QuoteResult(
        ticker=quote.ticker,
        price=quote.price,
        evaluated=len(kandydaci),
        triggered=[AlertRead.model_validate(a) for a in uruchomione],
    )
