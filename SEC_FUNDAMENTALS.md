# SEC Company Fundamentals

The app imports company-reported facts from SEC EDGAR's public Company Facts
data for held US-listed stocks and ETFs. No SEC API key is needed. The importer
uses the SEC ticker-to-CIK mapping and Company Facts JSON endpoints.

## Setup and sync

Set a descriptive `SEC_USER_AGENT` in `.env` with a contact email, as required
by SEC fair-access guidance:

```env
SEC_USER_AGENT=AI Investment Desk contact: you@example.com
```

Apply database migrations and start or restart the app:

```bash
alembic upgrade head
python run.py
```

Then fetch facts for current positive-quantity holdings:

```bash
curl -X POST http://localhost:8000/api/fundamentals/sync/sec
```

The endpoint stores supported annual income/cash-flow facts and the latest
reported balance-sheet facts. Re-running it updates existing filing records
instead of duplicating them.

## Valuation agent outputs

When filed data and compatible stored prices are available, the valuation agent
reports revenue, net income, diluted EPS, total assets, total liabilities,
stockholders' equity, operating cash flow, capital expenditures, net profit
margin, free cash flow, and P/E. P/E uses the latest annual diluted EPS and a
stored USD share price. Each reported fact includes its units, period, filing
date, form, and source.

SEC filings are periodic, not live. The set of facts varies by company, and
missing or incompatible values remain unavailable rather than being inferred.
The importer currently supports US-GAAP tags for domestic SEC filers; it does
not calculate a debt-to-equity ratio, forecast earnings, or replace review of
the original filings.
