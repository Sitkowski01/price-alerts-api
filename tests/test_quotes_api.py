NOTOWANIE_TS = "2026-08-27T10:00:00+00:00"


async def utworz_alert(client, naglowki, **nadpisania):
    dane = {"ticker": "CDR", "direction": "above", "threshold": "100.00"} | nadpisania
    res = await client.post("/v1/alerts", json=dane, headers=naglowki)
    return res.json()


async def wyslij(client, naglowki, *, ticker="CDR", price="150", ts=NOTOWANIE_TS):
    return await client.post(
        "/v1/quotes",
        json={"ticker": ticker, "price": price, "quote_ts": ts},
        headers=naglowki,
    )


class TestUruchamianie:
    async def test_cena_powyzej_progu_uruchamia_alert(self, client, naglowki):
        alert = await utworz_alert(client, naglowki)

        res = await wyslij(client, naglowki, price="150")

        body = res.json()
        assert res.status_code == 200
        assert body["evaluated"] == 1
        assert [a["id"] for a in body["triggered"]] == [alert["id"]]
        assert body["triggered"][0]["status"] == "triggered"

    async def test_cena_ponizej_progu_nie_uruchamia(self, client, naglowki):
        await utworz_alert(client, naglowki)

        body = (await wyslij(client, naglowki, price="99.99")).json()

        assert body["evaluated"] == 1
        assert body["triggered"] == []

    async def test_cena_rowna_progowi_uruchamia(self, client, naglowki):
        await utworz_alert(client, naglowki)

        body = (await wyslij(client, naglowki, price="100")).json()

        assert len(body["triggered"]) == 1

    async def test_alert_w_dol_uruchamia_sie_ponizej_progu(self, client, naglowki):
        await utworz_alert(client, naglowki, direction="below", threshold="100")

        body = (await wyslij(client, naglowki, price="80")).json()

        assert len(body["triggered"]) == 1

    async def test_notowanie_innego_instrumentu_nie_rusza_alertu(self, client, naglowki):
        await utworz_alert(client, naglowki, ticker="CDR")

        body = (await wyslij(client, naglowki, ticker="PKN", price="9999")).json()

        assert body["evaluated"] == 0
        assert body["triggered"] == []

    async def test_ticker_notowania_jest_normalizowany(self, client, naglowki):
        await utworz_alert(client, naglowki, ticker="CDR")

        body = (await wyslij(client, naglowki, ticker="  cdr  ", price="150")).json()

        assert len(body["triggered"]) == 1

    async def test_alert_wylaczony_nie_jest_oceniany(self, client, naglowki):
        alert = await utworz_alert(client, naglowki)
        await client.patch(
            f"/v1/alerts/{alert['id']}", json={"status": "disabled"}, headers=naglowki
        )

        body = (await wyslij(client, naglowki, price="9999")).json()

        assert body["evaluated"] == 0

    async def test_alert_juz_uruchomiony_nie_uruchamia_sie_drugi_raz(self, client, naglowki):
        await utworz_alert(client, naglowki)
        await wyslij(client, naglowki, price="150")

        body = (await wyslij(client, naglowki, price="160", ts="2026-08-27T11:00:00+00:00")).json()

        assert body["evaluated"] == 0
        assert body["triggered"] == []

    async def test_wiele_alertow_na_jeden_instrument(self, client, naglowki):
        await utworz_alert(client, naglowki, threshold="100")
        await utworz_alert(client, naglowki, threshold="140")
        await utworz_alert(client, naglowki, threshold="200")

        body = (await wyslij(client, naglowki, price="150")).json()

        assert body["evaluated"] == 3
        assert len(body["triggered"]) == 2


class TestIdempotencja:
    async def test_powtorzone_notowanie_nie_tworzy_drugiego_wpisu(self, client, naglowki):
        # Retry z kolejki albo ponowna wysylka nie moga podwoic historii.
        alert = await utworz_alert(client, naglowki)
        await wyslij(client, naglowki, price="150", ts=NOTOWANIE_TS)

        # Uzbrajamy alert ponownie i odtwarzamy to samo notowanie.
        await client.patch(f"/v1/alerts/{alert['id']}", json={"status": "armed"}, headers=naglowki)
        powtorka = (await wyslij(client, naglowki, price="150", ts=NOTOWANIE_TS)).json()

        assert powtorka["triggered"] == []

        historia = (await client.get(f"/v1/alerts/{alert['id']}/triggers")).json()
        assert len(historia) == 1

    async def test_nowe_notowanie_po_ponownym_uzbrojeniu_zapisuje_sie(self, client, naglowki):
        alert = await utworz_alert(client, naglowki)
        await wyslij(client, naglowki, price="150", ts=NOTOWANIE_TS)
        await client.patch(f"/v1/alerts/{alert['id']}", json={"status": "armed"}, headers=naglowki)

        await wyslij(client, naglowki, price="155", ts="2026-08-28T10:00:00+00:00")

        historia = (await client.get(f"/v1/alerts/{alert['id']}/triggers")).json()
        assert len(historia) == 2


class TestHistoria:
    async def test_zapisuje_cene_i_znacznik_czasu(self, client, naglowki):
        alert = await utworz_alert(client, naglowki)
        await wyslij(client, naglowki, price="150.25", ts=NOTOWANIE_TS)

        historia = (await client.get(f"/v1/alerts/{alert['id']}/triggers")).json()

        assert len(historia) == 1
        assert historia[0]["price"] == "150.250000"
        assert historia[0]["alert_id"] == alert["id"]

    async def test_historia_nieistniejacego_alertu_to_404(self, client):
        res = await client.get("/v1/alerts/00000000-0000-0000-0000-000000000000/triggers")
        assert res.status_code == 404

    async def test_usuniecie_alertu_kasuje_jego_historie(self, client, naglowki, session):
        from sqlalchemy import func, select

        from app.models import Trigger

        alert = await utworz_alert(client, naglowki)
        await wyslij(client, naglowki, price="150")

        await client.delete(f"/v1/alerts/{alert['id']}", headers=naglowki)

        pozostalo = await session.scalar(select(func.count()).select_from(Trigger))
        assert pozostalo == 0


class TestAutoryzacja:
    async def test_notowanie_bez_klucza_to_401(self, client):
        res = await client.post(
            "/v1/quotes",
            json={"ticker": "CDR", "price": "150", "quote_ts": NOTOWANIE_TS},
        )
        assert res.status_code == 401
