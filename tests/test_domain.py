from decimal import Decimal

import pytest

from app.domain import AlertRule, AlertStatus, Direction, normalize_ticker, should_trigger


def regula(direction: Direction, threshold: str, status: AlertStatus = AlertStatus.ARMED):
    return AlertRule(ticker="CDR", direction=direction, threshold=Decimal(threshold), status=status)


class TestNormalizacjaTickera:
    @pytest.mark.parametrize(
        ("wejscie", "oczekiwane"),
        [
            ("cdr", "CDR"),
            ("  cdr  ", "CDR"),
            ("CDR", "CDR"),
            ("Cd R", "CD R"),
            ("", ""),
        ],
    )
    def test_sprowadza_do_wersalikow_i_przycina(self, wejscie, oczekiwane):
        assert normalize_ticker(wejscie) == oczekiwane


class TestProgWGore:
    @pytest.mark.parametrize(
        ("cena", "uruchamia"),
        [
            ("99.999999", False),
            ("100", True),  # rowna progowi — prog jest domkniety
            ("100.000001", True),
            ("250", True),
        ],
    )
    def test_uruchamia_od_progu_w_gore(self, cena, uruchamia):
        assert should_trigger(regula(Direction.ABOVE, "100"), Decimal(cena)) is uruchamia


class TestProgWDol:
    @pytest.mark.parametrize(
        ("cena", "uruchamia"),
        [
            ("100.000001", False),
            ("100", True),
            ("99.999999", True),
            ("1", True),
        ],
    )
    def test_uruchamia_od_progu_w_dol(self, cena, uruchamia):
        assert should_trigger(regula(Direction.BELOW, "100"), Decimal(cena)) is uruchamia


class TestStanAlertu:
    @pytest.mark.parametrize("status", [AlertStatus.TRIGGERED, AlertStatus.DISABLED])
    def test_alert_nieuzbrojony_nie_reaguje_na_nic(self, status):
        # Nawet cena grubo za progiem nie rusza alertu, ktory juz zadzialal
        # albo zostal wylaczony.
        assert should_trigger(regula(Direction.ABOVE, "100", status), Decimal("9999")) is False

    def test_alert_uzbrojony_reaguje(self):
        assert should_trigger(regula(Direction.ABOVE, "100"), Decimal("101")) is True


class TestPrecyzja:
    def test_grosze_nie_gina_na_zaokragleniu(self):
        # Decimal, nie float: 0.1 + 0.2 we floatach nie jest rowne 0.3.
        prog = regula(Direction.ABOVE, "0.3")
        assert should_trigger(prog, Decimal("0.1") + Decimal("0.2")) is True
