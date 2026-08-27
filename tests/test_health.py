class TestHealth:
    async def test_liveness_nie_dotyka_bazy(self, client):
        # Chwilowa awaria Postgresa nie moze kazac Kubernetesowi ubic poda.
        res = await client.get("/healthz")

        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    async def test_readiness_sprawdza_baze(self, client):
        res = await client.get("/readyz")

        assert res.status_code == 200
        assert res.json()["database"] == "reachable"


class TestMetryki:
    async def test_metrics_wystawia_format_prometheusa(self, client):
        await client.get("/healthz")

        res = await client.get("/metrics")

        assert res.status_code == 200
        assert "http_requests_total" in res.text


class TestCors:
    async def test_zapytanie_z_dozwolonego_origin_dostaje_naglowek(self, client):
        # Klient webowy chodzi po przeglądarce — bez tego nagłówka
        # przeglądarka odrzuca odpowiedź, choć serwer ją wysłał.
        res = await client.get("/v1/alerts", headers={"Origin": "http://localhost:5173"})

        assert res.status_code == 200
        assert res.headers["access-control-allow-origin"] == "http://localhost:5173"

    async def test_preflight_przepuszcza_naglowek_z_kluczem(self, client):
        res = await client.options(
            "/v1/alerts",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )

        assert res.status_code == 200
        assert "x-api-key" in res.headers["access-control-allow-headers"].lower()

    async def test_obcy_origin_nie_dostaje_zgody(self, client):
        res = await client.get("/v1/alerts", headers={"Origin": "https://zlosliwa.example"})

        assert "access-control-allow-origin" not in res.headers
