"""
Portfolio service - business logic for portfolio operations
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import httpx
import logging
from app.models import (
    Asset, Holding, Transaction, Price, PortfolioSnapshot, MacroIndicator,
    ExchangeRate, AssetType, BrokerType, TransactionType, CompanyNews,
    CompanyFinancialFact,
)
from app.schemas import (
    PortfolioSummary, HoldingResponse, BrokerPortfolio
)
from app.data_sources.fred import FREDFetcher
from app.data_sources.frankfurter import FrankfurterFetcher
from app.brokers.etoro import EtoroAPIError, EtoroMarketDataClient
from app.data_sources.sec import (
    SEC_COMPANY_FACTS_URL,
    SEC_TICKERS_URL,
    build_ticker_map,
    extract_company_facts,
)

logger = logging.getLogger(__name__)


class SECFundamentalsService:
    """Fetch and persist annual SEC company facts for current portfolio holdings."""

    def __init__(
        self,
        db: Session,
        user_agent: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.db = db
        self.user_agent = user_agent.strip()
        self.transport = transport

    async def sync_portfolio_facts(self) -> Dict:
        if not self.user_agent or "@" not in self.user_agent:
            return {
                "status": "error",
                "message": "SEC_USER_AGENT must identify the application and include a contact email.",
            }

        symbols = [
            row[0]
            for row in self.db.query(Asset.symbol)
            .join(Holding, Holding.asset_id == Asset.id)
            .filter(Holding.quantity > 0)
            .distinct()
            .order_by(Asset.symbol)
            .all()
        ]
        if not symbols:
            return {
                "status": "success",
                "symbols": 0,
                "facts_stored": 0,
                "errors": [],
            }

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        errors = []
        stored = 0
        updated = 0
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                ticker_response = await client.get(SEC_TICKERS_URL)
                ticker_response.raise_for_status()
                ticker_map = build_ticker_map(ticker_response.json())

                for symbol in symbols:
                    cik = ticker_map.get(symbol.upper())
                    if cik is None:
                        errors.append(f"{symbol}: ticker not found in SEC company list")
                        continue

                    try:
                        response = await client.get(
                            SEC_COMPANY_FACTS_URL.format(cik=cik)
                        )
                        response.raise_for_status()
                        facts = extract_company_facts(response.json())
                        if not facts:
                            errors.append(f"{symbol}: no supported annual facts found")
                            continue

                        for fact in facts:
                            existing = (
                                self.db.query(CompanyFinancialFact)
                                .filter(
                                    CompanyFinancialFact.symbol == symbol,
                                    CompanyFinancialFact.metric == fact["metric"],
                                    CompanyFinancialFact.accession_number
                                    == fact["accession_number"],
                                )
                                .one_or_none()
                            )
                            if existing:
                                existing.value = Decimal(fact["value"])
                                existing.units = fact["units"]
                                existing.period_start = fact["period_start"]
                                existing.period_end = fact["period_end"]
                                existing.filed_date = fact["filed_date"]
                                existing.form = fact["form"]
                                existing.fetched_at = datetime.utcnow()
                                updated += 1
                            else:
                                fact_values = {
                                    **fact,
                                    "value": Decimal(fact["value"]),
                                }
                                self.db.add(
                                    CompanyFinancialFact(
                                        symbol=symbol,
                                        source="SEC EDGAR",
                                        **fact_values,
                                    )
                                )
                                stored += 1
                        self.db.commit()
                    except (httpx.HTTPError, ValueError, KeyError) as exc:
                        self.db.rollback()
                        logger.exception("SEC facts fetch failed for %s", symbol)
                        errors.append(f"{symbol}: {exc}")
        except (httpx.HTTPError, ValueError) as exc:
            self.db.rollback()
            logger.exception("SEC company ticker lookup failed")
            return {"status": "error", "message": str(exc)}

        return {
            "status": "partial" if errors else "success",
            "symbols": len(symbols),
            "facts_stored": stored,
            "facts_updated": updated,
            "errors": errors,
        }


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
        observed_at = datetime.utcnow()
        PortfolioService.update_market_prices(
            db,
            {
                symbol: (price, observed_at, source, None)
                for symbol, (price, source) in prices.items()
            },
        )

    @staticmethod
    def update_market_prices(
        db: Session,
        prices: Dict[str, Tuple[Decimal, datetime, str, Optional[str]]],
    ) -> None:
        """Store timestamped market prices and update current holding valuations."""
        for symbol, (price, price_date, source, currency) in prices.items():
            asset = db.query(Asset).filter(Asset.symbol == symbol).first()
            if asset:
                price_record = Price(
                    asset_id=asset.id,
                    price=price,
                    price_date=price_date,
                    source=source,
                    currency=currency,
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
            if not any(data.values()):
                return {
                    "status": "error",
                    "message": "FRED returned no observations for the requested daily series.",
                }
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
            if not any(data.values()):
                return {
                    "status": "error",
                    "message": "FRED returned no observations for the requested monthly series.",
                }
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
                    description=article.description,
                    url=article.url,
                    source=article.source,
                    published_date=article.published_date
                )
                db.add(news)
                stored += 1
            elif not existing.description and article.description:
                existing.description = article.description

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
                    "description": a.description,
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
                "description": a.description,
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
                "description": a.description,
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


class EtoroPriceService:
    """Fetch and persist eToro stock, ETF, and crypto prices in USD."""

    SUPPORTED_ASSET_TYPES = (AssetType.STOCK, AssetType.ETF, AssetType.CRYPTO)

    def __init__(self, db: Session, client: Optional[EtoroMarketDataClient] = None):
        self.db = db
        if client is None:
            from app.config import settings

            client = EtoroMarketDataClient(
                api_key=settings.etoro_api_key,
                user_key=settings.etoro_user_key,
            )
        self.client = client

    async def sync_portfolio_prices(self) -> Dict:
        assets = (
            self.db.query(Asset)
            .join(Holding, Holding.asset_id == Asset.id)
            .filter(
                Holding.quantity > 0,
                Asset.asset_type.in_(self.SUPPORTED_ASSET_TYPES),
            )
            .distinct()
            .order_by(Asset.symbol)
            .all()
        )
        if not assets:
            return {
                "status": "success",
                "currency": "USD",
                "assets": 0,
                "prices_updated": 0,
                "errors": [],
            }

        errors: List[str] = []
        asset_by_instrument_id = {}

        async with self.client as client:
            for asset in assets:
                if asset.etoro_instrument_id is not None:
                    asset_by_instrument_id[asset.etoro_instrument_id] = asset
                    continue
                try:
                    instrument_id = await client.resolve_instrument_id(asset.symbol)
                except EtoroAPIError as exc:
                    logger.error("eToro symbol lookup failed for %s: %s", asset.symbol, exc)
                    errors.append(f"{asset.symbol}: {exc}")
                    continue
                if instrument_id is None:
                    errors.append(f"{asset.symbol}: no exact eToro instrument match")
                    continue
                asset.etoro_instrument_id = instrument_id
                asset_by_instrument_id[instrument_id] = asset

            updates = {}
            instrument_ids = list(asset_by_instrument_id)
            for offset in range(0, len(instrument_ids), client.MAX_INSTRUMENTS_PER_REQUEST):
                batch = instrument_ids[offset:offset + client.MAX_INSTRUMENTS_PER_REQUEST]
                try:
                    quotes = await client.get_quotes(batch)
                except EtoroAPIError as exc:
                    symbols = ", ".join(
                        asset_by_instrument_id[instrument_id].symbol
                        for instrument_id in batch
                    )
                    logger.error("eToro price request failed for %s: %s", symbols, exc)
                    errors.extend(
                        f"{asset_by_instrument_id[instrument_id].symbol}: {exc}"
                        for instrument_id in batch
                    )
                    continue

                for instrument_id in batch:
                    asset = asset_by_instrument_id[instrument_id]
                    quote = quotes.get(instrument_id)
                    if quote is None:
                        errors.append(f"{asset.symbol}: eToro returned no valid quote")
                        continue
                    updates[asset.symbol] = (
                        quote.price_usd,
                        quote.price_date,
                        "etoro",
                        "USD",
                    )

        PortfolioService.update_market_prices(self.db, updates)
        if not updates and errors:
            status = "error"
        elif errors:
            status = "partial"
        else:
            status = "success"
        return {
            "status": status,
            "currency": "USD",
            "assets": len(assets),
            "prices_updated": len(updates),
            "symbols_updated": sorted(updates),
            "errors": errors,
        }

    @staticmethod
    def get_latest_portfolio_prices(db: Session) -> List[Dict]:
        assets = (
            db.query(Asset)
            .join(Price, Price.asset_id == Asset.id)
            .filter(
                Price.source == "etoro",
                Asset.asset_type.in_(EtoroPriceService.SUPPORTED_ASSET_TYPES),
            )
            .distinct()
            .order_by(Asset.symbol)
            .all()
        )
        latest_prices = []
        for asset in assets:
            price = (
                db.query(Price)
                .filter(Price.asset_id == asset.id, Price.source == "etoro")
                .order_by(Price.price_date.desc(), Price.id.desc())
                .first()
            )
            if price is None:
                continue
            latest_prices.append(
                {
                    "symbol": asset.symbol,
                    "asset_type": asset.asset_type.value,
                    "price": price.price,
                    "currency": price.currency,
                    "price_date": price.price_date.isoformat(),
                    "source": price.source,
                }
            )
        return latest_prices
