"""
Pydantic schemas for API requests/responses
"""
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from app.models import AssetType, BrokerType, TransactionType


class AssetBase(BaseModel):
    symbol: str
    name: str
    asset_type: AssetType
    isin: Optional[str] = None
    currency: str = "EUR"


class AssetCreate(AssetBase):
    pass


class AssetResponse(AssetBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HoldingResponse(BaseModel):
    id: int
    asset_id: str
    broker: BrokerType
    quantity: Decimal
    average_cost: Decimal
    total_cost: Decimal
    current_price: Optional[Decimal]
    current_value: Optional[Decimal]
    gain_loss: Optional[Decimal] = None
    gain_loss_percent: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    asset: Optional[AssetResponse] = None

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    asset_id: str
    broker: BrokerType
    transaction_type: TransactionType
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    commission: Decimal = Decimal("0")
    transaction_date: datetime
    settlement_date: Optional[datetime] = None
    notes: Optional[str] = None


class TransactionResponse(TransactionCreate):
    id: int
    broker_transaction_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PriceResponse(BaseModel):
    id: int
    asset_id: str
    price: Decimal
    price_date: datetime
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    total_value: Decimal
    total_cost: Decimal
    total_gain_loss: Decimal
    total_gain_loss_percent: float
    cash_value: Decimal
    holdings_count: int
    assets_count: int


class PortfolioSnapshot(BaseModel):
    snapshot_date: datetime
    total_value: Decimal
    total_cost: Decimal
    total_gain_loss: Decimal
    total_gain_loss_percent: float
    cash_value: Decimal

    class Config:
        from_attributes = True


class BrokerPortfolio(BaseModel):
    broker: BrokerType
    total_value: Decimal
    total_cost: Decimal
    holdings: List[HoldingResponse]
