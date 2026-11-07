# AI Investment Desk - Development Guide

## Project Overview

Personal AI Investment Desk is an AI-powered investment management platform that consolidates portfolios across multiple brokers (Scalable Capital, Binance) and provides portfolio tracking, market intelligence, and automated trading capabilities.

## Architecture

### Backend (Python/FastAPI)
- **Database**: PostgreSQL for portfolio history, transactions, market data
- **API**: FastAPI with async support
- **Services**: Business logic layer for portfolio operations
- **Brokers**: Abstract interface + implementations for each broker
- **Models**: SQLAlchemy ORM for all entities

### Key Modules
- `app/models.py` - Database schema (Asset, Holding, Transaction, Price, etc.)
- `app/schemas.py` - Pydantic request/response models
- `app/services.py` - Portfolio business logic
- `app/brokers/__init__.py` - Broker integration interface and VirtualBroker
- `app/routes.py` - API endpoints
- `app/main.py` - FastAPI app setup

## Development Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 14+

### Local Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env

# Set up PostgreSQL database
createdb ai_investment_desk

# Run migrations (when added)
alembic upgrade head

# Start server
python run.py
```

## Development Workflow

### Phase 1: Portfolio Consolidation (Current)
- [x] Database schema and models
- [x] Virtual broker for testing
- [x] Portfolio service with CRUD operations
- [x] API endpoints for portfolio management
- [ ] Real broker integrations (Scalable Capital, Binance)
- [ ] Dashboard/frontend

### Phase 2: Market Intelligence
- Market data pipelines
- Price update mechanisms
- News collection and analysis

### Phase 3: AI Assistant
- LLM integration
- Portfolio analysis
- Evidence-grounded decision support (read-only; no trade execution)

### Phase 4: Trading Automation
- Strategy backtesting
- Paper trading
- Live trading with risk controls

## API Endpoints (Phase 1)

```
GET    /api/portfolio/summary              # Portfolio overview
GET    /api/portfolio/holdings              # All holdings
GET    /api/portfolio/holdings/{broker}     # Holdings by broker
POST   /api/portfolio/sync/virtual          # Load virtual broker data
GET    /api/portfolio/transactions          # Transaction history
POST   /api/portfolio/transactions          # Add manual transaction
POST   /api/portfolio/snapshot              # Create daily snapshot
```

## Testing

### With Virtual Broker
1. Start the server: `python run.py`
2. POST to `/api/portfolio/sync/virtual` to load sample data
3. GET `/api/portfolio/summary` to see portfolio overview
4. GET `/api/portfolio/holdings` to view all holdings

### Database Inspection
```bash
psql ai_investment_desk
\dt                    # List tables
SELECT * FROM holdings; # View holdings
```

## Code Style
- Use type hints throughout
- Decimal for financial values (never float)
- Async/await for broker APIs
- Services handle business logic, routes handle HTTP
- Models are thin - logic lives in services

## Key Design Decisions

1. **Virtual Broker First**: Allows testing without real credentials
2. **Decimal for Money**: Precision matters in finance
3. **Service Layer**: Separates business logic from HTTP layer
4. **Abstract Broker Interface**: Easy to add new integrations
5. **Historical Snapshots**: Enables portfolio tracking over time

## Environment Variables

See `.env.example` for required configuration:
- `DATABASE_URL` - PostgreSQL connection string
- `SCALABLE_CAPITAL_API_KEY/SECRET` - Broker credentials
- `BINANCE_API_KEY/SECRET` - Broker credentials
- `DEBUG` - Development mode flag

## Next Steps

1. Set up PostgreSQL locally
2. Run `python run.py` to start the server
3. Test with `/api/portfolio/sync/virtual` endpoint
4. Start implementing real broker integrations
5. Build frontend dashboard

## Troubleshooting

**Database connection fails**: Check DATABASE_URL and PostgreSQL is running
```bash
psql -U user -h localhost -d ai_investment_desk
```

**Import errors**: Ensure virtual environment is activated and dependencies installed
```bash
source venv/bin/activate
pip install -r requirements.txt
```
