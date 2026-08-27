from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class StrEnumType(TypeDecorator):
    """Kolumna VARCHAR, która po odczycie oddaje element enuma, a nie goły string.

    Bez tego `alert.direction` wracał z bazy jako `str`, więc porównanie
    `rule.direction is Direction.ABOVE` było zawsze fałszywe i żaden alert
    się nie uruchamiał. Typ pilnuje tego w jednym miejscu, zamiast liczyć
    na rzutowanie w każdym wywołaniu.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[StrEnum], length: int) -> None:
        self.enum_class = enum_class
        super().__init__(length=length)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self.enum_class(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum_class(value)
