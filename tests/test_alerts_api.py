import pytest


async def utworz(client, naglowki, **nadpisania):
    dane = {"ticker": "CDR", "direction": "above", "threshold": "100.00"} | nadpisania
    return await client.post("/v1/alerts", json=dane, headers=naglowki)


class TestAutoryzacja:
    async def test_tworzenie_bez_klucza_konczy_sie_401(self, client):
        res = await client.post(
            "/v1/alerts", json={"ticker": "CDR", "direction": "above", "threshold": "100"}
        )
        assert res.status_code == 401

    async def test_bledny_klucz_konczy_sie_401(self, client):
        res = await utworz(client, {"X-API-Key": "nie-ten"})
        assert res.status_code == 401

    async def test_odczyt_nie_wymaga_klucza(self, client):
        res = await client.get("/v1/alerts")
        assert res.status_code == 200


class TestTworzenie:
    async def test_zwraca_201_i_uzbrojony_alert(self, client, naglowki):
        res = await utworz(client, naglowki)

        assert res.status_code == 201
        body = res.json()
        assert body["ticker"] == "CDR"
        assert body["status"] == "armed"
        assert body["id"]

    async def test_normalizuje_ticker(self, client, naglowki):
        res = await utworz(client, naglowki, ticker="  cdr  ")
        assert res.json()["ticker"] == "CDR"

    @pytest.mark.parametrize("prog", ["0", "-1", "-0.000001"])
    async def test_odrzuca_prog_niedodatni(self, client, naglowki, prog):
        res = await utworz(client, naglowki, threshold=prog)
        assert res.status_code == 422

    async def test_odrzuca_nieznany_kierunek(self, client, naglowki):
        res = await utworz(client, naglowki, direction="sideways")
        assert res.status_code == 422

    async def test_odrzuca_pusty_ticker(self, client, naglowki):
        res = await utworz(client, naglowki, ticker="   ")
        assert res.status_code == 422


class TestOdczyt:
    async def test_szczegoly_po_id(self, client, naglowki):
        alert_id = (await utworz(client, naglowki)).json()["id"]

        res = await client.get(f"/v1/alerts/{alert_id}")

        assert res.status_code == 200
        assert res.json()["id"] == alert_id

    async def test_nieistniejacy_alert_to_404(self, client):
        res = await client.get("/v1/alerts/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404

    async def test_niepoprawny_uuid_to_422(self, client):
        res = await client.get("/v1/alerts/nie-uuid")
        assert res.status_code == 422


class TestListowanie:
    async def test_filtruje_po_tickerze_bez_wzgledu_na_wielkosc_liter(self, client, naglowki):
        await utworz(client, naglowki, ticker="CDR")
        await utworz(client, naglowki, ticker="PKN")

        res = await client.get("/v1/alerts", params={"ticker": "cdr"})

        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["ticker"] == "CDR"

    async def test_filtruje_po_kierunku(self, client, naglowki):
        await utworz(client, naglowki, direction="above")
        await utworz(client, naglowki, direction="below")

        res = await client.get("/v1/alerts", params={"direction": "below"})

        assert res.json()["total"] == 1

    async def test_filtruje_po_statusie(self, client, naglowki):
        alert_id = (await utworz(client, naglowki)).json()["id"]
        await client.patch(f"/v1/alerts/{alert_id}", json={"status": "disabled"}, headers=naglowki)
        await utworz(client, naglowki, ticker="PKN")

        res = await client.get("/v1/alerts", params={"status": "disabled"})

        assert res.json()["total"] == 1

    async def test_stronicowanie_zwraca_calkowita_liczbe(self, client, naglowki):
        for i in range(5):
            await utworz(client, naglowki, ticker=f"AB{i}")

        res = await client.get("/v1/alerts", params={"limit": 2, "offset": 0})

        body = res.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2

    async def test_limit_jest_przycinany_do_maksimum(self, client, naglowki):
        # Bez gornego limitu jeden klient poprosilby o cala tabele.
        res = await client.get("/v1/alerts", params={"limit": 100_000})
        assert res.json()["limit"] == 200

    async def test_limit_zero_jest_odrzucany(self, client):
        res = await client.get("/v1/alerts", params={"limit": 0})
        assert res.status_code == 422


class TestZmianaIUsuniecie:
    async def test_zmienia_prog(self, client, naglowki):
        alert_id = (await utworz(client, naglowki)).json()["id"]

        res = await client.patch(
            f"/v1/alerts/{alert_id}", json={"threshold": "250.5"}, headers=naglowki
        )

        assert res.status_code == 200
        assert res.json()["threshold"] == "250.500000"

    async def test_zmiana_bez_klucza_to_401(self, client, naglowki):
        alert_id = (await utworz(client, naglowki)).json()["id"]

        res = await client.patch(f"/v1/alerts/{alert_id}", json={"threshold": "250"})

        assert res.status_code == 401

    async def test_pominiete_pola_zostaja_nietkniete(self, client, naglowki):
        alert_id = (await utworz(client, naglowki, note="pierwotna")).json()["id"]

        res = await client.patch(
            f"/v1/alerts/{alert_id}", json={"threshold": "111"}, headers=naglowki
        )

        assert res.json()["note"] == "pierwotna"

    async def test_usuwa_i_zwraca_204(self, client, naglowki):
        alert_id = (await utworz(client, naglowki)).json()["id"]

        res = await client.delete(f"/v1/alerts/{alert_id}", headers=naglowki)

        assert res.status_code == 204
        assert (await client.get(f"/v1/alerts/{alert_id}")).status_code == 404

    async def test_usuniecie_nieistniejacego_to_404(self, client, naglowki):
        res = await client.delete(
            "/v1/alerts/00000000-0000-0000-0000-000000000000", headers=naglowki
        )
        assert res.status_code == 404
