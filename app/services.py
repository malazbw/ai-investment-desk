"""
Portfolio service - business logic for portfolio operations
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
from app.models import (
    Asset, Holding, Transaction, Price, PortfolioSnapshot, MacroIndicator,
    ExchangeRate, AssetType, BrokerType, TransactionType, CompanyNews
)
from app.schemas import (
    PortfolioSummary, HoldingResponse, BrokerPortfolio
)
from app.data_sources.fred import FREDFetcher
from app.data_sources.frankfurter import FrankfurterFetcher

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for portfolio operations"""

    @staticmethod
    def get_or_create_asset(
        db: Session,
        symbol: str,
        name: str,
        asset_type: AssetType,
        isin: Optional[str] = None
    ) -> Asset:
        """Get existing asset or create new one"""
        asset = db.query(Asset).filter(Asset.symbol == symbol).first()
        if not asset:
            asset = Asset(
                id=symbol,
                symbol=symbol,
                name=name,
                asset_type=asset_type,
                isin=isin
            )
            db.add(asset)
            db.commit()
        return asset

    @staticmethod
    def add_transaction(
        db: Session,
        asset_id: str,
        broker: BrokerType,
        transaction_type: TransactionType,
        quantity: Decimal,
        price: Decimal,
        total_amount: Decimal,
        transaction_date: datetime,
        commission: Decimal = Decimal("0"),
        broker_transaction_id: Optional[str] = None
    ) -> Transaction:
        """Add a transaction and update holdings"""
        transaction = Transaction(
            asset_id=asset_id,
            broker=broker,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            total_amount=total_amount,
            commission=commission,
            transaction_date=transaction_date,
            broker_transaction_id=broker_transaction_id
        )
        db.add(transaction)

        # Update or create holding
        holding = db.query(Holding).filter(
            Holding.asset_id == asset_id,
            Holding.broker == broker
        ).first()

        if transaction_type == TransactionType.BUY:
            if not holding:
                holding = Holding(
                    asset_id=asset_id,
                    broker=broker,
                    quantity=quantity,
                    average_cost=price,
                    total_cost=total_amount - commission
                )
                db.add(holding)
            else:
                # Update average cost and total cost
                old_total_cost = holding.total_cost
                new_total_cost = old_total_cost + total_amount - commission
                new_quantity = holding.quantity + quantity
                holding.average_cost = new_total_cost / new_quantity
                holding.total_cost = new_total_cost
                holding.quantity = new_quantity

        elif transaction_type == TransactionType.SELL:
            if holding:
                holding.quantity -= quantity
                if holding.quantity > 0:
                    holding.total_cost = holding.average_cost * holding.quantity
                elif holding.quantity <= 0:
                    holding.quantity = Decimal("0")
                    holding.total_cost = Decimal("0")
                    holding.average_cost = Decimal("0")

        db.commit()
        return transaction

    @staticmethod
    def update_prices(
        db: Session,
        prices: Dict[str, Tuple[Decimal, str]]  # {symbol: (price, source)}
    ):
        """Update current prices for holdings"""
        for symbol, (price, source) in prices.items():
            asset = db.query(Asset).filter(Asset.symbol == symbol).first()
            if asset:
                price_record = Price(
                    asset_id=asset.id,
                    price=price,
                    price_date=datetime.utcnow(),
                    source=source
                )
                db.add(price_record)

                # Update current price on holdings
                holdings = db.query(Holding).filter(Holding.asset_id == asset.id).all()
                for holding in holdings:
                    holding.current_price = price
                    holding.current_value = holding.quantity * price

        db.commit()

    @staticmethod
    def get_portfolio_summary(db: Session) -> PortfolioSummary:
        """Calculate portfolio summary"""
        holdings = db.query(Holding).all()

        total_value = Decimal("0")
        total_cost = Decimal("0")

        for holding in holdings:
            if holding.current_value:
                total_value += holding.current_value
            total_cost += holding.total_cost

        total_gain_loss = total_value - total_cost
        total_gain_loss_percent = float(
            (total_gain_loss / total_cost * 100) if total_cost > 0 else 0
        )

        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_gain_loss=total_gain_loss,
            total_gain_loss_percent=total_gain_loss_percent,
            cash_value=Decimal("0"),  # TODO: Add cash tracking
            holdings_count=len(holdings),
            assets_count=len(set(h.asset_id for h in holdings))
        )

    @staticmethod
    def get_holdings_by_broker(db: Session, broker: BrokerType) -> List[HoldingResponse]:
        """Get holdings for a specific broker"""
        holdings = db.query(Holding).filter(Holding.broker == broker).all()
        return [
            HoldingResponse(
                **{c.name: getattr(h, c.name) for c in Holding.__table__.columns},
                asset=h.asset,
                gain_loss=(h.current_value - h.total_cost) if h.current_value else None,
                gain_loss_percent=float(
                    ((h.current_value - h.total_cost) / h.total_cost * 100)
                    if h.current_value and h.total_cost > 0 else 0
                )
            )
            for h in holdings
        ]

    @staticmethod
    def get_all_holdings(db: Session) -> List[HoldingResponse]:
        """Get all holdings across all brokers"""
        holdings = db.query(Holding).all()
        return [
            HoldingResponse(
                **{c.name: getattr(h, c.name) for c in Holding.__table__.columns},
                asset=h.asset,
                gain_loss=(h.current_value - h.total_cost) if h.current_value else None,
                gain_loss_percent=float(
                    ((h.current_value - h.total_cost) / h.total_cost * 100)
                    if h.current_value and h.total_cost > 0 else 0
                )
            )
            for h in holdings
        ]

    @staticmethod
    def get_recent_transactions(db: Session, days: int = 30) -> List[Transaction]:
        """Get recent transactions for portfolio analysis"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        transactions = db.query(Transaction).filter(
            Transaction.transaction_date >= cutoff_date
        ).order_by(Transaction.transaction_date.desc()).all()
        return transactions

    @staticmethod
    def create_snapshot(db: Session):
        """Create a daily portfolio snapshot"""
        summary = PortfolioService.get_portfolio_summary(db)
        snapshot = PortfolioSnapshot(
            snapshot_date=datetime.utcnow(),
            total_value=summary.total_value,
            total_cost=summary.total_cost,
            total_gain_loss=summary.total_gain_loss,
            total_gain_loss_percent=summary.total_gain_loss_percent,
            cash_value=summary.cash_value
        )
        db.add(snapshot)
        db.commit()
        return snapshot


class MacroDataService:
    """Service for macroeconomic data operations"""

    def __init__(self, db: Session, fred_api_key: str):
        self.db = db
        self.fred = FREDFetcher(fred_api_key)

    def fetch_and_store_daily_macro(self, start_date: Optional[str] = None) -> Dict:
        """Fetch and store daily macro data (VIX, DFF, DGS10)"""
        try:
            logger.info("Starting daily macro data fetch...")
            data = self.fred.fetch_daily_series(start_date)
            count = self._store_macro_data(data)
            logger.info(f"Successfully stored {count} daily macro records")
            return {"status": "success", "records_stored": count, "series": list(data.keys())}
        except Exception as e:
            logger.error(f"Error fetching daily macro data: {e}")
            return {"status": "error", "message": str(e)}

    def fetch_and_store_monthly_macro(self, start_date: Optional[str] = None) -> Dict:
        """Fetch and store monthly macro data (CPI)"""
        try:
            logger.info("Starting monthly macro data fetch...")
            data = self.fred.fetch_monthly_series(start_date)
            count = self._store_macro_data(data)
            logger.info(f"Successfully stored {count} monthly macro records")
            return {"status": "success", "records_stored": count, "series": list(data.keys())}
        except Exception as e:
            logger.error(f"Error fetching monthly macro data: {e}")
            return {"status": "error", "message": str(e)}

    def _store_macro_data(self, data: Dict[str, List[Tuple[str, Decimal]]]) -> int:
        """Store macro data in database, avoiding duplicates"""
        count = 0

        for series_id, observations in data.items():
            if not observations:
                logger.warning(f"No observations for {series_id}")
                continue

            series_info = FREDFetcher.SERIES.get(series_id, {})
            units = series_info.get("units", "")

            for date_str, value in observations:
                observation_date = datetime.strptime(date_str, "%Y-%m-%d")
                existing = self.db.query(MacroIndicator).filter(
                    MacroIndicator.series_id == series_id,
                    MacroIndicator.date == observation_date
                ).first()

                if not existing:
                    record = MacroIndicator(
                        series_id=series_id,
                        date=observation_date,
                        value=value,
                        units=units,
                        fetched_at=datetime.utcnow(),
                        source="FRED"
                    )
                    self.db.add(record)
                    count += 1

        self.db.commit()
        return count

    def get_latest_macro_data(self) -> Dict:
        """Get latest values for each macro series"""
        result = {}

        for series_id in FREDFetcher.SERIES.keys():
            latest = self.db.query(MacroIndicator).filter(
                MacroIndicator.series_id == series_id
            ).order_by(MacroIndicator.date.desc()).first()

            if latest:
                result[series_id] = {
                    "date": latest.date.isoformat(),
                    "value": float(latest.value),
                    "units": latest.units,
                    "name": FREDFetcher.SERIES[series_id]["name"]
                }

        return result

    def get_macro_series(self, series_id: str, days: int = 30) -> List[Dict]:
        """Get historical data for a macro series"""
        records = self.db.query(MacroIndicator).filter(
            MacroIndicator.series_id == series_id
        ).order_by(MacroIndicator.date.desc()).limit(days).all()

        return [
            {
                "date": r.date.isoformat(),
                "value": float(r.value),
                "units": r.units
            }
            for r in reversed(records)
        ]


class ExchangeRateService:
    """Fetch and query daily reference exchange rates."""

    def __init__(self, db: Session):
        self.db = db
        self.fetcher = FrankfurterFetcher()

    def fetch_and_store_daily_rates(self, start_date: Optional[str] = None) -> Dict:
        """Fetch rates from the requested date and upsert each currency/date pair."""
        try:
            observations = self.fetcher.fetch_rates(start_date)
            inserted = 0
            updated = 0
            fetched_at = datetime.utcnow()

            for observation_date, base_currency, quote_currency, rate in observations:
                existing = self.db.query(ExchangeRate).filter(
                    ExchangeRate.date == observation_date,
                    ExchangeRate.base_currency == base_currency,
                    ExchangeRate.quote_currency == quote_currency,
                ).first()

                if existing:
                    if existing.rate != rate:
                        existing.rate = rate
                        existing.fetched_at = fetched_at
                        updated += 1
                else:
                    self.db.add(ExchangeRate(
                        date=observation_date,
                        base_currency=base_currency,
                        quote_currency=quote_currency,
                        rate=rate,
                        source="Frankfurter",
                        fetched_at=fetched_at,
                    ))
                    inserted += 1

            self.db.commit()
            return {
                "status": "success",
                "records_inserted": inserted,
                "records_updated": updated,
                "observations_received": len(observations),
                "base_currency": FrankfurterFetcher.BASE_CURRENCY,
                "quote_currencies": list(FrankfurterFetcher.QUOTE_CURRENCIES),
            }
        except Exception as exc:
            self.db.rollback()
            logger.exception("Failed to fetch or store exchange rates")
            return {"status": "error", "message": str(exc)}

    def get_latest_rates(self, base_currency: str = "EUR") -> List[Dict]:
        """Return the newest stored observation for each quote currency."""
        latest_by_quote = []
        for quote_currency in FrankfurterFetcher.QUOTE_CURRENCIES:
            record = self.db.query(ExchangeRate).filter(
                ExchangeRate.base_currency == base_currency.upper(),
                ExchangeRate.quote_currency == quote_currency,
            ).order_by(ExchangeRate.date.desc()).first()
            if record:
                latest_by_quote.append(self._serialize_rate(record))
        return latest_by_quote

    def get_rate_history(
        self,
        base_currency: str,
        quote_currency: str,
        limit: int = 1095,
    ) -> List[Dict]:
        """Return stored observations for one currency pair, oldest first."""
        records = self.db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == base_currency.upper(),
            ExchangeRate.quote_currency == quote_currency.upper(),
        ).order_by(ExchangeRate.date.desc()).limit(limit).all()
        return [self._serialize_rate(record) for record in reversed(records)]

    @staticmethod
    def _serialize_rate(record: ExchangeRate) -> Dict:
        return {
            "date": record.date.isoformat(),
            "base_currency": record.base_currency,
            "quote_currency": record.quote_currency,
            "rate": float(record.rate),
            "source": record.source,
        }


class NewsService:
    """Service for managing company news"""

    @staticmethod
    def get_portfolio_symbols(db: Session) -> List[str]:
        """Get all unique symbols in current portfolio"""
        holdings = db.query(Holding).all()
        symbols = list(set(h.asset_id for h in holdings))
        logger.info(f"Found {len(symbols)} unique symbols in portfolio: {symbols}")
        return symbols

    @staticmethod
    async def fetch_and_store_portfolio_news(db: Session, days: int = 7) -> Dict:
        """Fetch news for all portfolio stocks and store in database"""
        from app.data_sources.news_fetcher import fetch_news_for_stocks

        try:
            symbols = NewsService.get_portfolio_symbols(db)

            if not symbols:
                logger.warning("No symbols in portfolio")
                return {"status": "success", "symbols": 0, "articles_stored": 0}

            all_news = await fetch_news_for_stocks(symbols, days=days)

            total_stored = 0
            for symbol, articles in all_news.items():
                stored = NewsService._store_articles(db, symbol, articles)
                total_stored += stored
                logger.info(f"Stored {stored} new articles for {symbol}")

            logger.info(f"Total articles stored: {total_stored}")
            return {
                "status": "success",
                "symbols": len(symbols),
                "articles_stored": total_stored,
                "symbols_list": symbols
            }

        except Exception as e:
            logger.error(f"Error fetching portfolio news: {e}")
            db.rollback()
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _store_articles(db: Session, symbol: str, articles: List) -> int:
        """Store articles in database, avoiding duplicates"""
        stored = 0

        asset = db.query(Asset).filter(Asset.id == symbol).first()
        if not asset:
            logger.warning(f"Symbol {symbol} not in assets, skipping")
            return 0

        for article in articles:
            existing = db.query(CompanyNews).filter(
                CompanyNews.url == article.url
            ).first()

            if not existing:
                news = CompanyNews(
                    symbol=symbol,
                    headline=article.headline,
                    url=article.url,
                    source=article.source,
                    published_date=article.published_date
                )
                db.add(news)
                stored += 1

        db.commit()
        return stored

    @staticmethod
    def get_portfolio_news(db: Session, days: int = 7, limit: int = 50) -> Dict[str, List[Dict]]:
        """Get news for all portfolio stocks"""
        symbols = NewsService.get_portfolio_symbols(db)

        result = {}
        since_date = datetime.utcnow() - timedelta(days=days)

        for symbol in symbols:
            articles = db.query(CompanyNews).filter(
                CompanyNews.symbol == symbol,
                CompanyNews.published_date >= since_date
            ).order_by(CompanyNews.published_date.desc()).limit(limit).all()

            result[symbol] = [
                {
                    "id": a.id,
                    "headline": a.headline,
                    "url": a.url,
                    "source": a.source,
                    "published_date": a.published_date.isoformat(),
                    "fetched_at": a.fetched_at.isoformat()
                }
                for a in articles
            ]

        return result

    @staticmethod
    def get_symbol_news(db: Session, symbol: str, days: int = 30, limit: int = 20) -> List[Dict]:
        """Get news for specific symbol"""
        since_date = datetime.utcnow() - timedelta(days=days)

        articles = db.query(CompanyNews).filter(
            CompanyNews.symbol == symbol,
            CompanyNews.published_date >= since_date
        ).order_by(CompanyNews.published_date.desc()).limit(limit).all()

        return [
            {
                "id": a.id,
                "headline": a.headline,
                "url": a.url,
                "source": a.source,
                "published_date": a.published_date.isoformat(),
                "fetched_at": a.fetched_at.isoformat()
            }
            for a in articles
        ]

    @staticmethod
    def get_latest_news(db: Session, symbol: str, limit: int = 5) -> List[Dict]:
        """Get latest N articles for a symbol"""
        articles = db.query(CompanyNews).filter(
            CompanyNews.symbol == symbol
        ).order_by(CompanyNews.published_date.desc()).limit(limit).all()

        return [
            {
                "id": a.id,
                "headline": a.headline,
                "url": a.url,
                "source": a.source,
                "published_date": a.published_date.isoformat()
            }
            for a in articles
        ]

    @staticmethod
    def get_news_stats(db: Session) -> Dict:
        """Get statistics about stored news"""
        total_articles = db.query(func.count(CompanyNews.id)).scalar()
        unique_symbols = db.query(func.count(func.distinct(CompanyNews.symbol))).scalar()
        unique_sources = db.query(func.count(func.distinct(CompanyNews.source))).scalar()
        latest_article = db.query(CompanyNews).order_by(
            CompanyNews.published_date.desc()
        ).first()

        return {
            "total_articles": total_articles,
            "unique_symbols": unique_symbols,
            "unique_sources": unique_sources,
            "latest_article_date": latest_article.published_date.isoformat() if latest_article else None
        }

    @staticmethod
    def analyze_symbol_news(db: Session, symbol: str, limit: int = 10) -> Dict:
        """Analyze news for a symbol with sentiment and themes"""
        articles = db.query(CompanyNews).filter(
            CompanyNews.symbol == symbol
        ).order_by(CompanyNews.published_date.desc()).limit(limit).all()

        if not articles:
            return {"symbol": symbol, "analysis": "No news found"}

        headlines = [a.headline.lower() for a in articles]

        positive_keywords = ["gain", "rally", "surge", "jump", "strong", "beat", "growth", "record", "success", "opportunity"]
        negative_keywords = ["drop", "fall", "decline", "loss", "crash", "weakness", "risk", "concern", "warning", "challenge"]

        positive_count = sum(1 for h in headlines if any(kw in h for kw in positive_keywords))
        negative_count = sum(1 for h in headlines if any(kw in h for kw in negative_keywords))
        neutral_count = len(articles) - positive_count - negative_count

        sentiment = "Mixed"
        if positive_count > negative_count * 1.5:
            sentiment = "Bullish"
        elif negative_count > positive_count * 1.5:
            sentiment = "Bearish"

        themes = []
        if any("earn" in h for h in headlines):
            themes.append("Earnings")
        if any("product" in h or "launch" in h or "ai" in h for h in headlines):
            themes.append("Innovation")
        if any("regulation" in h or "legal" in h or "compliance" in h for h in headlines):
            themes.append("Regulatory")
        if any("market" in h or "economy" in h for h in headlines):
            themes.append("Market Conditions")

        return {
            "symbol": symbol,
            "total_articles": len(articles),
            "sentiment": sentiment,
            "breakdown": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count
            },
            "themes": themes if themes else ["General News"],
            "latest_headline": articles[0].headline,
            "articles": [
                {
                    "headline": a.headline,
                    "source": a.source,
                    "published_date": a.published_date.isoformat()
                }
                for a in articles[:5]
            ]
        }
