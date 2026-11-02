# Daily Exchange-Rate Pipeline

The app fetches daily reference rates from the free Frankfurter API and stores them locally. No API key is required.

## Initial currencies

Rates use EUR as the base currency and currently include USD, GBP, and CHF. A rate such as `EUR/USD = 1.10` means one euro equals 1.10 US dollars.

## Data flow

Frankfurter API → `FrankfurterFetcher` → `ExchangeRateService` → PostgreSQL `exchange_rates` → `/api/exchange-rates` endpoints

The daily scheduler runs at 17:30 Europe/Berlin time. Each run re-fetches the last seven days to cover weekends, holidays, and publication delays. Existing date/currency pairs are updated if the provider revises a rate; new observations are inserted. A database uniqueness constraint protects each date/base/quote pair.

## Setup and migration

No environment variable or API key is needed. Apply the schema migration:

```bash
alembic upgrade head
```

## Manual fetch and backfill

Trigger the normal overlapping daily fetch:

```bash
curl -X POST http://localhost:8000/api/exchange-rates/sync
```

Backfill rates from a chosen date:

```bash
curl -X POST "http://localhost:8000/api/exchange-rates/sync?start_date=2023-11-02"
```

## Read stored data

Latest EUR rates:

```text
GET /api/exchange-rates/latest
```

History for a currency pair (up to 5,000 observations):

```text
GET /api/exchange-rates/history/EUR/USD?limit=1095
```

Rates are daily reference rates, not live or trade-time FX quotes.
