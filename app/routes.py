"""
API routes for portfolio management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import List, Dict
from datetime import date, datetime

from app.database import get_db
from app.models import BrokerType, AssetType, TransactionType
from app.schemas import (
    HoldingResponse, PortfolioSummary, TransactionResponse,
    TransactionCreate, BrokerPortfolio
)
from app.services import PortfolioService, MacroDataService
from app.services import ExchangeRateService
from app.brokers import VirtualBroker
from app.config import settings

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
macro_router = APIRouter(prefix="/api/macro", tags=["macro"])
exchange_rates_router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"])

# Initialize brokers
virtual_broker = VirtualBroker()


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(get_db)):
    """Get overall portfolio summary"""
    return PortfolioService.get_portfolio_summary(db)


@router.get("/holdings", response_model=List[HoldingResponse])
def get_all_holdings(db: Session = Depends(get_db)):
    """Get all holdings across all brokers"""
    return PortfolioService.get_all_holdings(db)


@router.get("/holdings/{broker}", response_model=List[HoldingResponse])
def get_broker_holdings(broker: BrokerType, db: Session = Depends(get_db)):
    """Get holdings for a specific broker"""
    return PortfolioService.get_holdings_by_broker(db, broker)


@router.post("/sync/virtual")
def sync_virtual_broker(db: Session = Depends(get_db)):
    """
    Load portfolio from virtual broker (for testing).
    This will populate the database with sample holdings and transactions.
    """
    import asyncio
    from app.models import Asset

    try:
        # Get holdings from virtual broker
        holdings = asyncio.run(virtual_broker.get_holdings())
        transactions = asyncio.run(virtual_broker.get_transactions())

        # Create assets from holdings
        for holding in holdings:
            PortfolioService.get_or_create_asset(
                db,
                symbol=holding.symbol,
                name=holding.symbol,
                asset_type=AssetType.STOCK,
            )

        # Load transactions
        for txn in transactions:
            asset = db.query(Asset).filter(Asset.symbol == txn.symbol).first()
            if not asset:
                asset = PortfolioService.get_or_create_asset(
                    db,
                    symbol=txn.symbol,
                    name=txn.symbol,
                    asset_type=AssetType.STOCK,
                )

            PortfolioService.add_transaction(
                db,
                asset_id=asset.id,
                broker=BrokerType.SCALABLE_CAPITAL,
                transaction_type=TransactionType(txn.transaction_type),
                quantity=txn.quantity,
                price=txn.price,
                total_amount=txn.quantity * txn.price,
                transaction_date=txn.timestamp,
                broker_transaction_id=txn.broker_id
            )

        # Update prices
        prices_dict = {
            h.symbol: (h.current_price, "virtual_broker")
            for h in holdings
        }
        PortfolioService.update_prices(db, prices_dict)

        return {
            "status": "synced",
            "holdings_loaded": len(holdings),
            "transactions_loaded": len(transactions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get transaction history"""
    from app.models import Transaction

    transactions = db.query(Transaction).offset(skip).limit(limit).all()
    return transactions


@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """Manually add a transaction"""
    txn = PortfolioService.add_transaction(
        db,
        asset_id=transaction.asset_id,
        broker=transaction.broker,
        transaction_type=transaction.transaction_type,
        quantity=transaction.quantity,
        price=transaction.price,
        total_amount=transaction.total_amount,
        commission=transaction.commission,
        transaction_date=transaction.transaction_date
    )
    return txn


@router.post("/snapshot")
def create_portfolio_snapshot(db: Session = Depends(get_db)):
    """Create a portfolio snapshot"""
    snapshot = PortfolioService.create_snapshot(db)
    return {
        "snapshot_id": snapshot.id,
        "snapshot_date": snapshot.snapshot_date,
        "total_value": snapshot.total_value
    }


@router.post("/sync/{broker}")
def sync_broker_portfolio(broker: BrokerType, db: Session = Depends(get_db)):
    """
    Sync portfolio from broker.
    TODO: Replace with real broker integrations.
    """
    if broker == BrokerType.SCALABLE_CAPITAL:
        raise HTTPException(
            status_code=501,
            detail="Scalable Capital integration coming soon"
        )
    elif broker == BrokerType.BINANCE:
        raise HTTPException(
            status_code=501,
            detail="Binance integration coming soon"
        )

    return {"status": "integration_pending"}


# Macro data endpoints
@macro_router.get("/latest", response_model=Dict)
def get_latest_macro(db: Session = Depends(get_db)):
    """Get latest values for all macro indicators"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.get_latest_macro_data()


@macro_router.get("/series/{series_id}")
def get_macro_series(series_id: str, days: int = 30, db: Session = Depends(get_db)):
    """Get historical data for a macro series"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.get_macro_series(series_id, days)


@macro_router.post("/jobs/daily")
def run_daily_macro_job(start_date: date | None = None, db: Session = Depends(get_db)):
    """Manually trigger daily macro data fetch (VIX, DFF, DGS10)"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.fetch_and_store_daily_macro(
        start_date.isoformat() if start_date else None
    )


@macro_router.post("/jobs/monthly")
def run_monthly_macro_job(start_date: date | None = None, db: Session = Depends(get_db)):
    """Manually trigger monthly macro data fetch (CPI)"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.fetch_and_store_monthly_macro(
        start_date.isoformat() if start_date else None
    )


@exchange_rates_router.get("/latest")
def get_latest_exchange_rates(db: Session = Depends(get_db)):
    """Get latest stored EUR exchange rates."""
    return ExchangeRateService(db).get_latest_rates()


@exchange_rates_router.get("/history/{base_currency}/{quote_currency}")
def get_exchange_rate_history(
    base_currency: str,
    quote_currency: str,
    limit: int = 1095,
    db: Session = Depends(get_db),
):
    """Get stored daily observations for a currency pair."""
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
    return ExchangeRateService(db).get_rate_history(base_currency, quote_currency, limit)


@exchange_rates_router.post("/sync")
def sync_exchange_rates(start_date: date | None = None, db: Session = Depends(get_db)):
    """Fetch daily exchange rates; optionally backfill from a start date."""
    result = ExchangeRateService(db).fetch_and_store_daily_rates(
        start_date.isoformat() if start_date else None
    )
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result["message"])
    return result
