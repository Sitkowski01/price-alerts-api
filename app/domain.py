"""Reguły alertów — czysta logika, bez bazy i bez HTTP.

Wydzielone celowo: to jest ta część, w której najłatwiej o błąd,
i jedyna, którą chce się testować bez podnoszenia czegokolwiek.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Direction(StrEnum):
    ABOVE = "above"
    BELOW = "below"


class AlertStatus(StrEnum):
    ARMED = "armed"
    TRIGGERED = "triggered"
    DISABLED = "disabled"


@dataclass(frozen=True)
class AlertRule:
    ticker: str
    direction: Direction
    threshold: Decimal
    status: AlertStatus


def normalize_ticker(ticker: str) -> str:
    """`  cdr  ` i `CDR` to ten sam instrument."""
    return ticker.strip().upper()


def should_trigger(rule: AlertRule, price: Decimal) -> bool:
    """Czy notowanie uruchamia alert.

    Próg jest domknięty z obu stron: cena równa progowi uruchamia alert.
    Alert, który nie jest uzbrojony, nie reaguje na nic.
    """
    if rule.status is not AlertStatus.ARMED:
        return False

    if rule.direction is Direction.ABOVE:
        return price >= rule.threshold
    return price <= rule.threshold
