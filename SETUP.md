# Local Development Setup Guide

## Prerequisites

Make sure you have:
- ✅ Docker Desktop installed and running
- ✅ Python 3.14+ installed
- ✅ Virtual environment already created (venv/)
- ✅ Dependencies installed (pip install -r requirements.txt)

## Quick Start (5 minutes)

### 1. Start PostgreSQL
```bash
docker-compose up -d
```

Verify it's running:
```bash
docker ps
# Should show: ai_investment_desk_db with status "healthy"
```

### 2. Run Migrations
```bash
source venv/bin/activate
alembic upgrade head
```

### 3. Start FastAPI Server
```bash
python run.py
```

The server will start on `http://localhost:8000`

### 4. In Another Terminal: Load Test Data
```bash
curl -X POST http://localhost:8000/api/portfolio/sync/virtual
```

Response should be:
```json
{
  "status": "synced",
  "holdings_loaded": 3,
  "transactions_loaded": 2
}
```

### 5. Check Your Portfolio
```bash
curl http://localhost:8000/api/portfolio/summary
```

Response:
```json
{
  "total_value": 12021.25,
  "total_cost": 10000,
  "total_gain_loss": 2021.25,
  "total_gain_loss_percent": 20.2,
  "holdings_count": 3,
  "assets_count": 3,
  "cash_value": 0
}
```

## Detailed Commands

### View API Documentation
Open in browser: http://localhost:8000/docs

### Get All Holdings
```bash
curl http://localhost:8000/api/portfolio/holdings
```

### Get Holdings by Broker
```bash
curl http://localhost:8000/api/portfolio/holdings/scalable_capital
```

### Get Transactions
```bash
curl http://localhost:8000/api/portfolio/transactions
```

### Run Tests
```bash
source venv/bin/activate
pytest tests/ -v
```

### Reset Database
```bash
./scripts/reset-db.sh
```

### Stop PostgreSQL
```bash
docker-compose down
```

Note: Data persists in Docker volume, container will restart next time you run `docker-compose up -d`

### Stop PostgreSQL and Delete Data
```bash
docker-compose down -v
```

Warning: This deletes all data! Only use for clean reset.

## Debugging

### PostgreSQL Connection Issues
```bash
# Check if container is running
docker ps | grep ai_investment_desk_db

# View container logs
docker-compose logs postgres

# Connect directly to database
docker exec -it ai_investment_desk_db psql -U investment_user -d ai_investment_desk
```

### Test Data Not Loading
```bash
# Verify server is running
curl http://localhost:8000/health

# Check for errors in server output
# (Look at terminal where you ran `python run.py`)

# Verify database tables exist
docker exec -it ai_investment_desk_db psql -U investment_user -d ai_investment_desk -c "\dt"
```

### Tests Failing
```bash
# Reset database
./scripts/reset-db.sh

# Run tests with verbose output
pytest tests/ -v -s

# Run single test
pytest tests/test_portfolio.py::test_health_check -v
```

## Environment Variables

Configured in `.env`:
- `DB_USER=investment_user` - PostgreSQL username
- `DB_PASSWORD=investment_password` - PostgreSQL password
- `DB_NAME=ai_investment_desk` - Database name
- `DATABASE_URL` - Full connection string (auto-generated)
- `DEBUG=True` - Enable debug mode

To change credentials, edit `.env` and restart: `docker-compose restart`

## File Structure

```
ai-investment-desk/
├── docker-compose.yml         # Docker PostgreSQL config
├── .env                        # Environment variables
├── alembic/                    # Database migrations
├── app/                        # FastAPI application
├── tests/                      # Test suite
├── scripts/
│   ├── setup.sh               # Complete setup script
│   └── reset-db.sh            # Reset database
├── run.py                      # Start FastAPI server
└── requirements.txt            # Python dependencies
```

## Typical Development Workflow

```bash
# Terminal 1: Start PostgreSQL and FastAPI
docker-compose up -d
source venv/bin/activate
alembic upgrade head
python run.py

# Terminal 2: Load test data and run tests
curl -X POST http://localhost:8000/api/portfolio/sync/virtual
pytest tests/ -v

# Terminal 3: Use API
curl http://localhost:8000/api/portfolio/summary
```

## Next Steps

Once this is working:
1. ✅ Database setup complete
2. 🔄 Implement Scalable Capital broker integration
3. 🔄 Implement Binance broker integration
4. 🔄 Build portfolio dashboard frontend
