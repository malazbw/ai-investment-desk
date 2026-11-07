# AI Investment Desk - Setup & Run Guide

## Quick Start (5 minutes)

### Prerequisites
- Python 3.10+
- Git

### Installation

```bash
# Clone/navigate to project
cd ai-investment-desk

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python3 init_db.py

# Start the server
python3 run.py
```

The API will be available at **http://localhost:8000**

---

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Testing the API

### Load Virtual Broker Sample Data
```bash
curl -X POST http://localhost:8000/api/portfolio/sync/virtual
```

### Prepare Current Research Data

Chat analysis reads stored data; it does not fetch live sources for every question.
Configure the relevant provider credentials, then sync the sources before testing:

```bash
# Requires FRED_API_KEY
curl -X POST http://localhost:8000/api/macro/jobs/daily
curl -X POST http://localhost:8000/api/macro/jobs/monthly

# Requires NEWSAPI_KEY
curl -X POST http://localhost:8000/api/news/fetch-portfolio

# Requires SEC_USER_AGENT with an identifying contact email
curl -X POST http://localhost:8000/api/fundamentals/sync/sec

# Requires ETORO_API_KEY and ETORO_USER_KEY
curl -X POST http://localhost:8000/api/prices/sync/etoro
```

The virtual broker deliberately supplies sample holdings and prices. Agent output
reports each price source; a `virtual_broker` quote must not be treated as a live
market price. News analysis uses headlines and, when provided by NewsAPI, a short
publisher description; it does not fetch full article text. Macro and company
fundamentals are based on the latest data stored from FRED and SEC filings,
respectively, and can lag current conditions.

Check the source and observation freshness currently stored by the app:

```bash
curl http://localhost:8000/api/portfolio/data-status
```

Portfolio summary amounts are combined only when holdings and their latest
prices use one matching currency. Mixed-currency totals and gains are reported
as unavailable rather than added together without conversion. A partial
valuation lists holdings without a usable stored price. Chat analysis is
read-only and reports source dates, currencies, and missing data when available.
The LangGraph assistant workflow asks the configured LLM to select relevant
specialists before they run. Simple portfolio lookups are answered directly from
stored portfolio data without an extra synthesis call; questions needing multiple
specialists are synthesized together. Routing uses one short model request.
The assistant is read-only and does not execute trades.

### Ask About a Company Outside Your Portfolio

The market-research agent recognizes explicit company names such as NVIDIA or
tickers such as `NVDA`. For a company that is not already held, it invokes an
on-demand research tool to request SEC company facts, an optional eToro quote,
and optional NewsAPI headlines/snippets. These results are returned as company
research only; the tool does not add the company to your holdings or save its
price/news as portfolio data. Configure `SEC_USER_AGENT`, `ETORO_API_KEY`,
`ETORO_USER_KEY`, and `NEWSAPI_KEY` to enable those sources. Each source reports
its own unavailable/error status, so the answer can still be partial.

### Get Portfolio Summary
```bash
curl http://localhost:8000/api/portfolio/summary
```

### Get All Holdings
```bash
curl http://localhost:8000/api/portfolio/holdings
```

### Get Transactions
```bash
curl http://localhost:8000/api/portfolio/transactions
```

### Create Portfolio Snapshot
```bash
curl -X POST http://localhost:8000/api/portfolio/snapshot
```

---

## Database Options

### Default: SQLite (Development)
- **No setup required**
- Database file: `ai_investment_desk.db`
- Best for: Local development, testing
- Run: Just follow Quick Start above

### PostgreSQL (Production)

#### Option 1: Using Docker Compose
```bash
# Requires Docker installed
docker-compose up -d

# Initialize database
docker exec ai_investment_desk_app python3 init_db.py
```

#### Option 2: Local PostgreSQL
```bash
# 1. Install PostgreSQL 14+
# macOS: brew install postgresql@16
# Ubuntu: sudo apt-get install postgresql
# Windows: https://www.postgresql.org/download/windows/

# 2. Create database
createdb ai_investment_desk

# 3. Set environment variable
export DATABASE_URL="postgresql://user:password@localhost:5432/ai_investment_desk"

# 4. Initialize tables
python3 init_db.py

# 5. Run server
python3 run.py
```

---

## Project Structure

```
ai-investment-desk/
├── app/
│   ├── main.py              # FastAPI app setup
│   ├── routes.py            # API endpoints
│   ├── models.py            # Database models (SQLAlchemy)
│   ├── schemas.py           # Request/response models (Pydantic)
│   ├── services.py          # Business logic
│   ├── database.py          # DB connection
│   ├── config.py            # Configuration
│   ├── scheduler.py         # Scheduled jobs (macro/FX data)
│   ├── brokers/
│   │   └── __init__.py      # Broker interfaces + VirtualBroker
│   └── data_sources/
│       ├── fred.py          # FRED API integration
│       └── frankfurter.py   # Exchange rates API
├── tests/
│   ├── test_portfolio.py
│   ├── test_macro_pipeline.py
│   └── test_exchange_rate_pipeline.py
├── run.py                   # Development server entry point
├── init_db.py              # Database initialization
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker setup
├── Dockerfile              # Container image
├── CLAUDE.md               # Project documentation
└── README.md               # This file
```

---

## Key Features

### Portfolio Management
- Consolidate holdings from multiple brokers
- Track transactions and cost basis
- Calculate gains/losses
- Daily portfolio snapshots

### Market Data
- Macro indicators (VIX, DFF, DGS10 from FRED API)
- Exchange rates (EUR/USD, EUR/GBP, etc.)
- eToro stock, ETF, and crypto prices stored in USD
- Automatic daily updates when eToro credentials are configured

### Virtual Broker
- Sample portfolio for testing
- No real credentials needed
- Perfect for development

---

## Environment Variables

### Optional Configuration File (.env)

```bash
# Database (optional, defaults to SQLite)
DATABASE_URL=postgresql://user:password@localhost:5432/ai_investment_desk

# FRED API (for macro data)
FRED_API_KEY=your_key_here

# eToro Public API (required for eToro price sync)
ETORO_API_KEY=your_public_api_key
ETORO_USER_KEY=your_user_key

# Broker Credentials (for future integrations)
SCALABLE_CAPITAL_API_KEY=xxx
SCALABLE_CAPITAL_API_SECRET=xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# App Settings
DEBUG=True
LOG_LEVEL=INFO
```

Create `.env` file in project root. The app will load it automatically.
After adding eToro price mapping and currency fields, apply database migrations
with `alembic upgrade head` before starting the app. The API keys are available
from the eToro account's API key management settings; read access is sufficient
for market-price retrieval.

Manually sync prices with `POST /api/prices/sync/etoro`, and retrieve the latest
stored portfolio prices with `GET /api/prices/latest`.
The sync normalizes market prices and current holding valuations to USD; it does
not convert previously recorded transactions or cost basis.

---

## Common Issues & Solutions

### "Database is locked" (SQLite)
- Only one Python process can write to SQLite at a time
- Solution: Restart the server or use PostgreSQL for production

### "Connection refused" (PostgreSQL)
- PostgreSQL service not running
- macOS: `brew services start postgresql@16`
- Ubuntu: `sudo systemctl start postgresql`

### "Module not found" errors
- Virtual environment not activated
- Run: `source venv/bin/activate`

### Port 8000 already in use
- Change port in `run.py` or kill the process:
- `lsof -ti:8000 | xargs kill -9`

---

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_portfolio.py

# Run with coverage
pytest --cov=app tests/
```

---

## Troubleshooting

### Fresh Start
If something breaks, reset everything:
```bash
# Remove database
rm ai_investment_desk.db

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Reinitialize
python3 init_db.py
python3 run.py
```

### Check Server Status
```bash
# Should return: {"status": "healthy"}
curl http://localhost:8000/health
```

### View Detailed Logs
Server logs are printed to console. For production, redirect to file:
```bash
python3 run.py > logs.txt 2>&1 &
tail -f logs.txt
```

---

## Next Development Steps

1. **Implement Real Broker APIs**
   - Scalable Capital integration
   - Binance integration
   - See: `app/brokers/__init__.py`

2. **Add Frontend Dashboard**
   - React/Vue.js dashboard
   - Charts and visualizations
   - Portfolio tracking over time

3. **AI Assistant**
   - LLM integration for investment advice
   - Portfolio optimization suggestions
   - Risk analysis

4. **Automated Trading**
   - Strategy backtesting
   - Paper trading
   - Live trading with risk controls

---

## API Endpoints Reference

### Portfolio
- `GET /api/portfolio/summary` - Overall portfolio stats
- `GET /api/portfolio/holdings` - All holdings
- `GET /api/portfolio/holdings/{broker}` - Holdings by broker
- `POST /api/portfolio/sync/virtual` - Load sample data
- `GET /api/portfolio/transactions` - Transaction history
- `POST /api/portfolio/transactions` - Add transaction
- `POST /api/portfolio/snapshot` - Create snapshot

### Market Data
- `GET /api/macro/latest` - Latest macro indicators
- `GET /api/macro/series/{series_id}` - Historical macro data
- `POST /api/macro/jobs/daily` - Manually fetch daily macro
- `POST /api/macro/jobs/monthly` - Manually fetch monthly macro
- `GET /api/exchange-rates/latest` - Latest FX rates
- `GET /api/exchange-rates/history/{base}/{quote}` - Historical rates
- `POST /api/exchange-rates/sync` - Manually fetch rates

### Health
- `GET /` - App info
- `GET /health` - Health check

---

## Support

For issues or questions:
1. Check this guide first
2. Review `CLAUDE.md` for architecture details
3. Check server logs (check console output)
4. Review test files for usage examples

---

**Last Updated**: 2026-11-02
**Python Version**: 3.10+
**Framework**: FastAPI
**Database**: SQLite (dev) / PostgreSQL (prod)
