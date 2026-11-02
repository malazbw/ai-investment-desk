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
- Automatic daily updates

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
