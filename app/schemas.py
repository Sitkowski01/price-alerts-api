import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import AlertStatus, Direction, normalize_ticker

Ticker = Annotated[str, Field(min_length=1, max_length=16)]
Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]


class AlertCreate(BaseModel):
    ticker: Ticker
    direction: Direction
    threshold: Money
    note: str | None = Field(default=None, max_length=280)

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized:
            raise ValueError("ticker nie może być pusty")
        return normalized


class AlertUpdate(BaseModel):
    threshold: Money | None = None
    status: AlertStatus | None = None
    note: str | None = Field(default=None, max_length=280)


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    direction: Direction
    threshold: Decimal
    status: AlertStatus
    note: str | None
    created_at: datetime
    updated_at: datetime


class TriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alert_id: uuid.UUID
    price: Decimal
    quote_ts: datetime
    created_at: datetime


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class AlertPage(Page):
    items: list[AlertRead]


class QuoteIn(BaseModel):
    ticker: Ticker
    price: Money
    quote_ts: datetime

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_ticker(value)


class QuoteResult(BaseModel):
    ticker: str
    price: Decimal
    evaluated: int
    triggered: list[AlertRead]
