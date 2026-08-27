import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain import AlertStatus, Direction
from app.types import StrEnumType


class Base(DeclarativeBase):
    pass


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[Direction] = mapped_column(StrEnumType(Direction, 8), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        StrEnumType(AlertStatus, 16), nullable=False, default=AlertStatus.ARMED
    )
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    triggers: Mapped[list["Trigger"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Reguly trzymamy takze w bazie: aplikacja nie jest jedyna droga do danych.
        CheckConstraint("threshold > 0", name="ck_alerts_threshold_positive"),
        CheckConstraint("direction in ('above','below')", name="ck_alerts_direction"),
        CheckConstraint("status in ('armed','triggered','disabled')", name="ck_alerts_status"),
        # Wyszukiwanie alertow do oceny notowania idzie dokladnie po tej parze.
        Index("ix_alerts_ticker_status", "ticker", "status"),
    )


class Trigger(Base):
    __tablename__ = "triggers"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quote_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    alert: Mapped[Alert] = relationship(back_populates="triggers")

    __table_args__ = (
        # Powtorzone notowanie (retry, replay z kolejki) nie tworzy drugiego wpisu.
        UniqueConstraint("alert_id", "quote_ts", name="uq_triggers_alert_quote_ts"),
        Index("ix_triggers_alert_created", "alert_id", "created_at"),
    )
