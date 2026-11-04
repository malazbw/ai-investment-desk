"""
Database models for AI Investment Desk
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Float, Date, DateTime, Integer, Enum, Text, Numeric, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class AssetType(str, enum.Enum):
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    CASH = "cash"


class BrokerType(str, enum.Enum):
    SCALABLE_CAPITAL = "scalable_capital"
    BINANCE = "binance"


class TransactionType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


class Asset(Base):
    """Asset master data"""
    __tablename__ = "assets"

    id = Column(String, primary_key=True)  # Unique identifier (ticker/symbol)
    symbol = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    asset_type = Column(Enum(AssetType), nullable=False)
    isin = Column(String, nullable=True, index=True)
    currency = Column(String, default="EUR")
    etoro_instrument_id = Column(Integer, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    holdings = relationship("Holding", back_populates="asset")
    prices = relationship("Price", back_populates="asset")
    transactions = relationship("Transaction", back_populates="asset")
    news = relationship("CompanyNews", back_populates="asset")
    financial_facts = relationship("CompanyFinancialFact", back_populates="asset")


class Holding(Base):
    """Current portfolio holdings"""
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False, index=True)
    broker = Column(Enum(BrokerType), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)  # Support fractions for crypto
    average_cost = Column(Numeric(15, 4), nullable=False)  # Cost per unit
    total_cost = Column(Numeric(20, 4), nullable=False)  # Total cost basis
    current_price = Column(Numeric(20, 8), nullable=True)
    current_value = Column(Numeric(20, 4), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asset = relationship("Asset", back_populates="holdings")
    __table_args__ = (
        Index("idx_holding_asset_broker", "asset_id", "broker"),
    )


class Transaction(Base):
    """Transaction history"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False, index=True)
    broker = Column(Enum(BrokerType), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(15, 4), nullable=False)
    total_amount = Column(Numeric(20, 4), nullable=False)
    commission = Column(Numeric(10, 4), default=0)
    transaction_date = Column(DateTime, nullable=False)
    settlement_date = Column(DateTime, nullable=True)
    broker_transaction_id = Column(String, nullable=True, unique=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="transactions")
    __table_args__ = (
        Index("idx_transaction_date", "transaction_date"),
        Index("idx_transaction_broker", "broker"),
    )


class Price(Base):
    """Historical price data"""
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False, index=True)
    price = Column(Numeric(20, 8), nullable=False)
    price_date = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)  # "broker_api", "market_data", etc.
    currency = Column(String(3), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="prices")
    __table_args__ = (
        Index("idx_price_date", "price_date"),
        Index("idx_price_asset_date", "asset_id", "price_date"),
    )


class PortfolioSnapshot(Base):
    """Daily portfolio snapshots for historical tracking"""
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_date = Column(DateTime, nullable=False, index=True)
    total_value = Column(Numeric(20, 4), nullable=False)
    total_cost = Column(Numeric(20, 4), nullable=False)
    total_gain_loss = Column(Numeric(20, 4), nullable=False)
    total_gain_loss_percent = Column(Float, nullable=False)
    cash_value = Column(Numeric(20, 4), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_snapshot_date", "snapshot_date"),
    )


class MacroIndicator(Base):
    """Macroeconomic indicators from FRED API"""
    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True)
    series_id = Column(String(10), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    value = Column(Numeric(15, 4), nullable=False)
    units = Column(String(50), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(20), default="FRED")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_macro_series_date", "series_id", "date"),
        Index("idx_macro_date", "date"),
    )


class ExchangeRate(Base):
    """Daily foreign exchange reference rates"""
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    base_currency = Column(String(3), nullable=False)
    quote_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(20, 10), nullable=False)
    source = Column(String(30), nullable=False, default="Frankfurter")
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "date",
            "base_currency",
            "quote_currency",
            name="uq_exchange_rate_date_pair",
        ),
        Index("idx_exchange_rate_pair_date", "base_currency", "quote_currency", "date"),
    )


class CompanyNews(Base):
    """News articles for portfolio stocks"""
    __tablename__ = "company_news"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, ForeignKey("assets.id"), nullable=False, index=True)
    headline = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=False, unique=True)
    source = Column(String, nullable=False)
    published_date = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="news")

    __table_args__ = (
        Index("idx_company_news_symbol_date", "symbol", "published_date"),
        Index("idx_company_news_date", "published_date"),
    )


class CompanyFinancialFact(Base):
    """Company-reported financial facts imported from SEC filings."""
    __tablename__ = "company_financial_facts"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, ForeignKey("assets.id"), nullable=False, index=True)
    metric = Column(String(50), nullable=False)
    value = Column(Numeric(30, 8), nullable=False)
    units = Column(String(30), nullable=False)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=False)
    filed_date = Column(Date, nullable=False)
    form = Column(String(10), nullable=False)
    accession_number = Column(String(25), nullable=False)
    source = Column(String(20), nullable=False, default="SEC EDGAR")
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    asset = relationship("Asset", back_populates="financial_facts")
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "metric",
            "accession_number",
            name="uq_company_financial_fact_filing",
        ),
        Index(
            "idx_company_financial_fact_symbol_metric_period",
            "symbol",
            "metric",
            "period_end",
        ),
    )
