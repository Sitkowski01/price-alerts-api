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
