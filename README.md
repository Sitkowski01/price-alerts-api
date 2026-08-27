# Price Alerts API

[![CI](https://github.com/Sitkowski01/price-alerts-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Sitkowski01/price-alerts-api/actions/workflows/ci.yml)

Serwis alertów cenowych: użytkownik zakłada regułę („daj znać, gdy CDR przebije 100 zł"),
a serwis ocenia napływające notowania i zapisuje historię uruchomień.

REST API w **FastAPI**, dane w **PostgreSQL**, wdrożenie w **Kubernetesie**.
Projekt jest celowo mały pod względem domeny, a rozbudowany pod względem tego,
co odróżnia usługę produkcyjną od skryptu: migracje, sondy, metryki, kontrola dostępu,
idempotencja i zachowanie przy równoległych zapytaniach.

Klient webowy do tego API: [**price-alerts-web**](https://github.com/Sitkowski01/price-alerts-web)
— Vue 3 z Composition API i Pinią.

Źródło notowań: [**quote-stream**](https://github.com/Sitkowski01/quote-stream)
— potok w Go, który czyta je z Kafki i wysyła tutaj przez `POST /v1/quotes`.

Infrastruktura: [**alerts-infra**](https://github.com/Sitkowski01/alerts-infra)
— Terraform stawiający klaster k3s na EC2 pod te manifesty.

## Model

Dwie tabele. `alerts` to reguła, `triggers` to historia jej zadziałań.

```
alerts                                triggers
------                                --------
id            uuid  PK                id         uuid PK
ticker        text                    alert_id   uuid FK -> alerts (ON DELETE CASCADE)
direction     above | below           price      numeric(18,6)
threshold     numeric(18,6)  > 0      quote_ts   timestamptz
status        armed | triggered       created_at timestamptz
              | disabled
note          text
created_at    timestamptz             UNIQUE (alert_id, quote_ts)
updated_at    timestamptz             INDEX  (alert_id, created_at)

INDEX (ticker, status)
```

Kwoty trzymane są jako `numeric`, nie `float` — na cenach zaokrąglenie binarne
potrafi zgubić grosze, a próg alertu jest porównaniem, nie szacunkiem.

## Endpointy

| Metoda | Ścieżka | Klucz | Opis |
|---|---|---|---|
| `POST` | `/v1/alerts` | tak | Zakłada alert (domyślnie uzbrojony) |
| `GET` | `/v1/alerts` | nie | Lista z filtrami `ticker`, `status`, `direction` i stronicowaniem |
| `GET` | `/v1/alerts/{id}` | nie | Szczegóły |
| `PATCH` | `/v1/alerts/{id}` | tak | Zmiana progu, notatki lub statusu (także ponowne uzbrojenie) |
| `DELETE` | `/v1/alerts/{id}` | tak | Usunięcie razem z historią |
| `GET` | `/v1/alerts/{id}/triggers` | nie | Historia uruchomień |
| `POST` | `/v1/quotes` | tak | Przyjmuje notowanie i ocenia alerty na ten instrument |
| `GET` | `/healthz` | nie | Liveness |
| `GET` | `/readyz` | nie | Readiness (sprawdza bazę) |
| `GET` | `/metrics` | nie | Metryki w formacie Prometheusa |

Zapisy wymagają nagłówka `X-API-Key`. Odczyty są otwarte — to nie są dane wrażliwe.
Dokumentacja OpenAPI generuje się sama pod `/docs`.

## Reguły, które serwis egzekwuje

- **Próg jest domknięty.** Cena równa progowi uruchamia alert.
- **Alert działa raz.** Po zadziałaniu przechodzi w `triggered` i przestaje reagować,
  dopóki ktoś go nie uzbroi ponownie.
- **Ticker jest normalizowany.** `  cdr  ` i `CDR` to ten sam instrument.
- **Powtórzone notowanie nie dubluje historii.** Ponowna wysyłka tego samego
  `(alert, znacznik czasu)` jest bez efektu — pilnuje tego unikalny indeks
  i `ON CONFLICT DO NOTHING`, a nie sprawdzenie „czy już istnieje", które byłoby wyścigiem.
- **Równoległe notowania nie zdublują uruchomienia.** Alerty są blokowane
  na czas transakcji (`SELECT ... FOR UPDATE`).
- **Reguły są też w bazie.** Dodatni próg i dozwolone wartości `direction` oraz `status`
  to `CHECK CONSTRAINT` — aplikacja nie jest jedyną drogą do danych.

## Uruchomienie

### Docker Compose — najkrótsza droga

```bash
cp .env.example .env       # ustaw API_KEY
docker compose up --build
```

Podnosi PostgreSQL, czeka aż baza faktycznie przyjmuje połączenia, wykonuje migracje
i startuje API na `http://localhost:8000`. Dokumentacja: `http://localhost:8000/docs`.

### Lokalnie, bez kontenera

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Przykład użycia

```bash
KLUCZ=zmien-mnie

# Alert: daj znac, gdy CDR wejdzie na 100 zl lub wyzej
curl -X POST localhost:8000/v1/alerts \
  -H "X-API-Key: $KLUCZ" -H "Content-Type: application/json" \
  -d "{\"ticker\":\"cdr\",\"direction\":\"above\",\"threshold\":\"100.00\"}"

# Notowanie ponizej progu — nic sie nie dzieje
curl -X POST localhost:8000/v1/quotes \
  -H "X-API-Key: $KLUCZ" -H "Content-Type: application/json" \
  -d "{\"ticker\":\"CDR\",\"price\":\"98.40\",\"quote_ts\":\"2026-08-27T10:00:00Z\"}"

# Notowanie powyzej progu — alert zadziala i przejdzie w stan triggered
curl -X POST localhost:8000/v1/quotes \
  -H "X-API-Key: $KLUCZ" -H "Content-Type: application/json" \
  -d "{\"ticker\":\"CDR\",\"price\":\"101.10\",\"quote_ts\":\"2026-08-27T10:05:00Z\"}"
```

## Wynik uruchomienia

Poniżej faktyczne odpowiedzi serwisu podniesionego przez `docker compose up`
(oba kontenery raportują `healthy`).

```
$ curl -s localhost:8000/readyz
{"status":"ok","database":"reachable"}

$ curl -s -X POST localhost:8000/v1/alerts -H "X-API-Key: $KLUCZ" ... -d '{"ticker":"cdr", ...}'
{"id":"34e163dc-...","ticker":"CDR","direction":"above","threshold":"100.000000",
 "status":"armed","note":"pozycja dluga", ...}

$ # ten sam POST bez naglowka X-API-Key
HTTP 401

$ # notowanie ponizej progu
{"ticker":"CDR","price":"98.40","evaluated":1,"triggered":[]}

$ # notowanie powyzej progu
{"ticker":"CDR","price":"101.10","evaluated":1,
 "triggered":[{"id":"34e163dc-...","status":"triggered", ...}]}

$ curl -s localhost:8000/v1/alerts/34e163dc-.../triggers
[{"alert_id":"34e163dc-...","price":"101.100000","quote_ts":"2026-08-27T10:05:00Z", ...}]
```

Ticker podany jako `cdr` wrócił jako `CDR`, próg zapisał się z pełną precyzją,
a alert przeszedł w `triggered` dopiero przy drugim notowaniu.

Metryki są etykietowane wzorcem trasy, nie konkretnym adresem — inaczej każdy
identyfikator zakładałby w Prometheusie osobną serię czasową:

```
http_requests_total{method="POST",path="/v1/alerts",status="201"} 1.0
http_requests_total{method="POST",path="/v1/alerts",status="401"} 1.0
http_requests_total{method="POST",path="/v1/quotes",status="200"} 2.0
http_requests_total{method="GET",path="/v1/alerts/{alert_id}/triggers",status="200"} 1.0
```

Logi wychodzą w JSON, z czasem obsługi i identyfikatorem zapytania:

```json
{"ts": "2026-08-27T13:23:24+00:00", "level": "INFO", "logger": "price_alerts",
 "message": "zapytanie obsłużone", "method": "GET", "path": "/metrics",
 "status_code": 200, "duration_ms": 3.14, "request_id": "2011c959-..."}
```

## Testy

```bash
uv run pytest -v
```

Dwie warstwy:

- **Testy domenowe** (`tests/test_domain.py`) — czysta logika progu, bez bazy i bez HTTP.
  Sprawdzają m.in. że próg jest domknięty, że alert nieuzbrojony nie reaguje na nic
  i że `Decimal("0.1") + Decimal("0.2")` przekracza próg `0.3` — na `float` by nie przekroczył.
- **Testy integracyjne** — przechodzą przez prawdziwy HTTP i prawdziwego PostgreSQL:
  autoryzacja, walidacja wejścia, filtry i stronicowanie, kaskadowe usuwanie,
  ocena notowań, idempotencja powtórzonego notowania oraz sondy.

Testy integracyjne wymagają bazy:

```bash
docker compose up -d db
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/price_alerts_test \
  uv run pytest -v
```

## Migracje

```bash
uv run alembic upgrade head        # w gore
uv run alembic downgrade base      # w dol
uv run alembic check               # czy model zgadza sie z migracjami
```

`alembic check` jest częścią CI. To on wychwytuje najczęstszy błąd w tej warstwie:
dodaną kolumnę w modelu, do której nikt nie dopisał migracji.

## Kubernetes

Manifesty leżą w `k8s/`, ponumerowane w kolejności stosowania.

```bash
docker build -t price-alerts-api:0.1.0 .

kubectl apply -f k8s/00-namespace.yaml
kubectl -n price-alerts create secret generic price-alerts-secret \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:haslo@host:5432/price_alerts" \
  --from-literal=API_KEY="..."
kubectl apply -f k8s/10-configmap.yaml -f k8s/20-migrate-job.yaml
kubectl -n price-alerts wait --for=condition=complete job/price-alerts-migrate --timeout=120s
kubectl apply -f k8s/30-deployment.yaml -f k8s/40-service.yaml \
              -f k8s/50-ingress.yaml -f k8s/60-hpa.yaml
```

### Szybka próba lokalnie (kind)

Bez chmury i bez kosztów. `k8s/dev/postgres.yaml` podnosi bazę w klastrze —
wyłącznie do prób, na produkcji baza jest usługą zarządzaną.

```bash
kind create cluster --name alerty
docker build -t price-alerts-api:0.1.0 .
kind load docker-image price-alerts-api:0.1.0 --name alerty

kubectl apply -f k8s/00-namespace.yaml -f k8s/dev/postgres.yaml
kubectl -n price-alerts wait --for=condition=available deployment/postgres --timeout=180s

kubectl -n price-alerts create secret generic price-alerts-secret \
  --from-literal=DATABASE_URL="postgresql+asyncpg://postgres:postgres@postgres:5432/price_alerts" \
  --from-literal=API_KEY="klucz-klastrowy"

kubectl apply -f k8s/10-configmap.yaml -f k8s/20-migrate-job.yaml
kubectl -n price-alerts wait --for=condition=complete job/price-alerts-migrate --timeout=180s
kubectl apply -f k8s/30-deployment.yaml -f k8s/40-service.yaml -f k8s/60-hpa.yaml

kubectl -n price-alerts port-forward svc/price-alerts-api 8080:80
kind delete cluster --name alerty      # sprzątanie
```

### Uruchomione na klastrze

Manifesty nie są teorią — poniżej stan po ich zastosowaniu na klastrze **kind**
(Kubernetes 1.34, lokalnie w Dockerze). Ta sama sekwencja działa na k3s;
na EKS zmienia się tylko klasa Ingressa i źródło sekretów.

```
$ kubectl -n price-alerts get pods,svc,deploy,job,hpa
NAME                                    READY   STATUS      RESTARTS   AGE
pod/postgres-f68d96f6b-dkqht            1/1     Running     0          2m16s
pod/price-alerts-api-6686cf5778-2dfgn   1/1     Running     0          31s
pod/price-alerts-api-6686cf5778-fmmqj   1/1     Running     0          23s
pod/price-alerts-migrate-99tps          0/1     Completed   0          45s

service/postgres           ClusterIP   10.96.248.64    5432/TCP
service/price-alerts-api   ClusterIP   10.96.175.128   80/TCP

deployment.apps/price-alerts-api   2/2     2            2
job.batch/price-alerts-migrate     Complete   1/1     10s

horizontalpodautoscaler/price-alerts-api  Deployment/price-alerts-api  2  6  2
```

Migracje wykonały się jako `Job`, zanim ruszyły pody aplikacji:

```
$ kubectl -n price-alerts logs job/price-alerts-migrate
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Tabele alertów i uruchomień
```

Pełny scenariusz przeszedł przez `Service`, z wnętrza klastra, na dwóch replikach —
łącznie z odrzuceniem zapisu bez nagłówka `X-API-Key` (HTTP 401) i uruchomieniem
alertu dopiero przy drugim notowaniu.

#### Sondy w praktyce

Podział liveness/readiness był sprawdzony, a nie tylko opisany. Po wyłączeniu bazy
(`kubectl scale deployment/postgres --replicas=0`):

```
price-alerts-api-...-8qxsl   READY=0/1   STATUS=Running   RESTARTS=0
price-alerts-api-...-grcv9   READY=0/1   STATUS=Running   RESTARTS=0
```

Pody wypadły z endpointów `Service` (`notReadyAddresses`), więc ruch przestał do nich
trafiać — ale **żaden nie został zrestartowany**. Po powrocie bazy obie repliki wróciły
do `READY 1/1`, wciąż z zerem restartów. Gdyby `/healthz` sprawdzał PostgreSQL,
Kubernetes ubiłby tu dwa całkowicie zdrowe procesy.

#### Czego readiness nie łapie

`/readyz` odpowiada na pytanie „czy ten pod dosięga bazy", a nie „czy baza jest poprawna".
Po restarcie deweloperskiego Postgresa (`emptyDir`, brak trwałości) `SELECT 1` nadal
przechodził, więc pody raportowały gotowość, a `/v1/alerts` zwracało 500 — schemat
zniknął razem z podem. To świadomy wybór: brakująca migracja jest problemem wdrożenia,
którego przekładanie podów i tak nie naprawi. Rozwiązaniem jest ponowne uruchomienie
`Joba` z migracjami, nie ostrzejsza sonda.

HPA pokazuje `cpu: <unknown>` — kind nie ma `metrics-server`. Na klastrze z metrykami
skalowanie działa; tutaj widać samą konfigurację.

### Uruchomione na AWS

Powyższe dotyczy klastra lokalnego. **28.08.2026 ten sam zestaw manifestów pojechał
na AWS** — instancja EC2 z k3s postawiona Terraformem z repozytorium
[alerts-infra](https://github.com/Sitkowski01/alerts-infra), region `eu-central-1`.

```
$ kubectl -n price-alerts get pods
pod/postgres-768dbdbb88-szhvr          1/1   Running     0   3m56s
pod/price-alerts-api-b67b8f585-4nq86   1/1   Running     0   48s
pod/price-alerts-api-b67b8f585-c5qtt   1/1   Running     0   48s
pod/price-alerts-migrate-p4zgr         0/1   Completed   0   61s

$ kubectl -n price-alerts logs job/price-alerts-migrate
INFO [alembic.runtime.migration] Running upgrade -> 0001, Tabele alertów i uruchomień
```

Scenariusz przeszedł przez `Service`, z wnętrza klastra, na dwóch replikach:

```
readyz:            {"status":"ok","database":"reachable"}
utworzenie alertu: HTTP 201
bez klucza:        HTTP 401
notowanie 98.40:   {"evaluated":1,"triggered":[]}
notowanie 101.10:  {"evaluated":1,"triggered":[{"status":"triggered", ...}]}
```

⚠ Instancja została **wyłączona po zrobieniu zrzutów** (`terraform destroy`).
To demo, nie działająca usługa — adres z tamtego uruchomienia już nie odpowiada.

Jedna rzecz, którą to wdrożenie zweryfikowało, a lokalny klaster nie:
**`t3.micro` nie udźwignie k3s.** Przy 1 GB RAM sam serwer k3s zajmował 553 MB,
wolnej pamięci zostawało 54 MB, obciążenie skakało do 9, a API nie wstawało
nawet po pół godzinie. Dopiero `t3.small` z 2 GB doprowadził węzeł do `Ready`.

Decyzje, które widać w manifestach:

- **Liveness nie dotyka bazy, readiness dotyka.** Gdyby `/healthz` sprawdzał PostgreSQL,
  chwilowa awaria bazy kazałaby Kubernetesowi restartować całkiem zdrowe pody.
  Readiness wypycha pod z Service, ale go nie zabija — to właściwa reakcja.
- **Startup probe przed liveness**, żeby wolny start nie wyglądał jak awaria.
- **Migracje jako `Job`, nie initContainer.** Przy trzech replikach initContainer
  oznaczałby trzy równoległe `alembic upgrade` na tej samej bazie.
- **Kontener nie jest rootem**, ma system plików tylko do odczytu i zrzucone wszystkie
  capabilities. `/tmp` jest podmontowany osobno, bo inaczej nie ma gdzie pisać.
- **`maxUnavailable: 0`** — wdrożenie nie zabiera mocy przerobowej, zanim nowy pod
  zgłosi gotowość.
- **W repozytorium nie ma manifestu `Secret` — nawet przykładowego.** Plik
  `kind: Secret` z wypełnionym `stringData` to dokładnie ten kształt, którego
  szukają skanery sekretów; trzymanie go w repo zapala alarm przy każdym pushu,
  choćby wartości były zmyślone. Sekret zakłada się komendą `kubectl create secret`
  (wyżej), a na klastrze produkcyjnym przez External Secrets Operator,
  Sealed Secrets albo AWS Secrets Manager.

### Uwaga o kosztach na AWS

**EKS jest płatny za sam działający control plane, nawet przy zerze podów.**
Do pokazania działającego klastra wystarczy **k3s na jednej instancji EC2**
z darmowego pułapu. Zanim cokolwiek odpalisz, ustaw alert budżetowy,
a instancję wyłącz po zrobieniu zrzutów ekranu.

## CI

`.github/workflows/ci.yml`, trzy zadania:

1. **Lint, testy i migracje** — ruff (lint i formatowanie), migracje w górę i w dół,
   `alembic check`, pełny `pytest` przeciw prawdziwemu PostgreSQL-owi
   podniesionemu jako usługa runnera.
2. **Walidacja manifestów** — `kubeconform` sprawdza `k8s/` względem schematów
   Kubernetesa. Bez klastra, przy każdym pushu.
3. **Budowa obrazu** — build wieloetapowy z cache warstw; na `main` obraz trafia
   do GHCR, na pull requeście jest tylko budowany.

## Stack

| Warstwa | Technologie |
|---|---|
| API | FastAPI, Pydantic v2, Uvicorn |
| Dane | PostgreSQL 17, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| Obserwowalność | prometheus-client, logi w JSON |
| Testy | pytest, pytest-asyncio, httpx |
| Jakość | ruff (lint + format) |
| Konteneryzacja | Docker (build wieloetapowy), Docker Compose |
| Orkiestracja | Kubernetes — Deployment, Service, Ingress, Job, HPA |
| CI | GitHub Actions, kubeconform, GHCR |
