"""
Portfolio service - business logic for portfolio operations
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import httpx
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
from app.data_sources.sec import (
    SEC_COMPANY_FACTS_URL,
    SEC_TICKERS_URL,
    build_ticker_map,
    extract_company_facts,
)
from app.brokers.etoro import EtoroAPIError

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for portfolio operations"""

    @staticmethod
    def get_or_create_asset(
        db: Session,
        symbol: str,
        name: str,
        asset_type: AssetType,
        isin: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Asset:
        """Get existing asset or create new one"""
        asset = db.query(Asset).filter(Asset.symbol == symbol).first()
        if not asset:
            asset = Asset(
                id=symbol,
                symbol=symbol,
                name=name,
                asset_type=asset_type,
                isin=isin,
                currency=currency or "EUR",
            )
            db.add(asset)
            db.commit()
        elif currency:
            asset.currency = currency.upper()
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
        if quantity <= 0 or price <= 0 or total_amount <= 0 or commission < 0:
            raise ValueError("Transaction amounts must be positive and commission non-negative")
        if broker_transaction_id:
            existing = db.query(Transaction).filter(
                Transaction.broker_transaction_id == broker_transaction_id
            ).first()
            if existing is not None:
                if (
                    existing.asset_id != asset_id
                    or existing.broker != broker
                    or existing.transaction_type != transaction_type
                    or existing.quantity != quantity
                    or existing.price != price
                    or existing.total_amount != total_amount
                    or existing.commission != commission
                    or existing.transaction_date != transaction_date
                ):
                    raise ValueError(
                        "Broker transaction ID already exists with different transaction data"
                    )
                return existing

        if db.query(Asset).filter(Asset.id == asset_id).first() is None:
            raise ValueError(f"Unknown asset: {asset_id}")

        holding = db.query(Holding).filter(
            Holding.asset_id == asset_id,
            Holding.broker == broker
        ).first()
        if (
            transaction_type == TransactionType.SELL
            and (holding is None or holding.quantity < quantity)
        ):
            raise ValueError("Cannot sell more units than are currently held")

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
        db.flush()
        for symbol, (price, source) in prices.items():
            asset = db.query(Asset).filter(Asset.symbol == symbol).first()
            if asset:
                latest = (
                    db.query(Price)
                    .filter(Price.asset_id == asset.id)
                    .order_by(Price.price_date.desc(), Price.id.desc())
                    .first()
                )
                if not (
                    source == "virtual_broker"
                    and latest is not None
                    and latest.source == source
                    and latest.price == price
                ):
                    db.add(Price(
                        asset_id=asset.id,
                        price=price,
                        price_date=datetime.utcnow(),
                        source=source,
                        currency=asset.currency,
                    ))

                # Update current price on holdings
                holdings = db.query(Holding).filter(Holding.asset_id == asset.id).all()
                for holding in holdings:
                    holding.current_price = price
                    holding.current_value = holding.quantity * price

        db.commit()

    @staticmethod
    def get_portfolio_summary(db: Session) -> PortfolioSummary:
        """Calculate a summary only when its amounts share a known currency."""
        holdings = db.query(Holding).all()
        if not holdings:
            return PortfolioSummary(
                total_value=Decimal("0"),
                total_cost=Decimal("0"),
                total_gain_loss=Decimal("0"),
                total_gain_loss_percent=0.0,
                cash_value=Decimal("0"),
                holdings_count=0,
                assets_count=0,
                valuation_status="empty",
            )

        currencies = {
            (holding.asset.currency or "EUR").upper()
            for holding in holdings
            if holding.asset is not None
        }
        unpriced_holdings = []
        unpriced_asset_ids = set()
        for holding in holdings:
            latest_price = (
                db.query(Price)
                .filter(Price.asset_id == holding.asset_id)
                .order_by(Price.price_date.desc(), Price.id.desc())
                .first()
            )
            price_currency = (
                (latest_price.currency or holding.asset.currency or "EUR").upper()
                if latest_price is not None and holding.asset is not None
                else (holding.asset.currency or "EUR").upper()
                if holding.asset is not None
                else None
            )
            if (
                holding.current_value is None
                or latest_price is None
                or (
                    holding.asset is not None
                    and price_currency != (holding.asset.currency or "EUR").upper()
                )
            ):
                unpriced_holdings.append(holding.asset.symbol if holding.asset else holding.asset_id)
                unpriced_asset_ids.add(holding.asset_id)
            if price_currency:
                currencies.add(price_currency)

        if len(currencies) > 1:
            total_value = total_cost = total_gain_loss = None
            total_gain_loss_percent = None
            currency = None
            valuation_status = "mixed_currency"
        else:
            currency = next(iter(currencies), None)
            total_cost = sum((holding.total_cost for holding in holdings), Decimal("0"))
            total_value = sum(
                (
                    holding.current_value
                    for holding in holdings
                    if holding.current_value is not None
                    and holding.asset_id not in unpriced_asset_ids
                ),
                Decimal("0"),
            )
            complete = not unpriced_holdings
            total_gain_loss = total_value - total_cost if complete else None
            total_gain_loss_percent = (
                float(total_gain_loss / total_cost * 100)
                if total_gain_loss is not None and total_cost > 0
                else 0.0
                if total_gain_loss is not None
                else None
            )
            valuation_status = "complete" if complete else "partial"

        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_gain_loss=total_gain_loss,
            total_gain_loss_percent=total_gain_loss_percent,
            cash_value=Decimal("0"),  # TODO: Add cash tracking
            holdings_count=len(holdings),
            assets_count=len(set(h.asset_id for h in holdings)),
            currency=currency,
            valuation_status=valuation_status,
            unpriced_holdings=sorted(set(unpriced_holdings)),
        )

    @staticmethod
    def get_data_status(db: Session) -> Dict[str, Dict]:
        """Summarize availability, provenance, and freshness of stored data."""
        now = datetime.utcnow()
        latest_price = (
            db.query(Price)
            .order_by(Price.price_date.desc(), Price.id.desc())
            .first()
        )
        latest_fact = (
            db.query(CompanyFinancialFact)
            .order_by(CompanyFinancialFact.filed_date.desc(), CompanyFinancialFact.id.desc())
            .first()
        )
        latest_news = (
            db.query(CompanyNews)
            .order_by(CompanyNews.published_date.desc(), CompanyNews.id.desc())
            .first()
        )
        latest_macro = (
            db.query(MacroIndicator)
            .order_by(MacroIndicator.date.desc(), MacroIndicator.id.desc())
            .first()
        )
        latest_fx = (
            db.query(ExchangeRate)
            .order_by(ExchangeRate.date.desc(), ExchangeRate.id.desc())
            .first()
        )

        def status(record, observed_at, source, count, max_age_days):
            if record is None:
                return {
                    "status": "not_synced",
                    "source": None,
                    "observed_at": None,
                    "fetched_at": None,
                    "records": 0,
                }
            observed_datetime = (
                datetime.combine(observed_at, datetime.min.time())
                if not isinstance(observed_at, datetime)
                else observed_at
            )
            age_days = (now - observed_datetime).total_seconds() / 86400
            return {
                "status": "fresh" if age_days <= max_age_days else "stale",
                "source": source,
                "observed_at": observed_at.isoformat(),
                "fetched_at": (
                    record.fetched_at.isoformat()
                    if getattr(record, "fetched_at", None)
                    else getattr(record, "created_at", now).isoformat()
                ),
                "records": count,
            }

        return {
            "prices": status(
                latest_price,
                latest_price.price_date if latest_price else None,
                latest_price.source if latest_price else None,
                db.query(func.count(Price.id)).scalar() or 0,
                3,
            ),
            "fundamentals": status(
                latest_fact,
                latest_fact.filed_date if latest_fact else None,
                latest_fact.source if latest_fact else None,
                db.query(func.count(CompanyFinancialFact.id)).scalar() or 0,
                550,
            ),
            "news": status(
                latest_news,
                latest_news.published_date if latest_news else None,
                latest_news.source if latest_news else None,
                db.query(func.count(CompanyNews.id)).scalar() or 0,
                7,
            ),
            "macro": status(
                latest_macro,
                latest_macro.date if latest_macro else None,
                latest_macro.source if latest_macro else None,
                db.query(func.count(MacroIndicator.id)).scalar() or 0,
                60,
            ),
            "exchange_rates": status(
                latest_fx,
                latest_fx.date if latest_fx else None,
                latest_fx.source if latest_fx else None,
                db.query(func.count(ExchangeRate.id)).scalar() or 0,
                10,
            ),
        }

    @staticmethod
    def get_holdings_by_broker(db: Session, broker: BrokerType) -> List[HoldingResponse]:
        """Get holdings for a specific broker"""
        holdings = db.query(Holding).filter(Holding.broker == broker).all()
        return PortfolioService._serialize_holdings(db, holdings)

    @staticmethod
    def get_all_holdings(db: Session) -> List[HoldingResponse]:
        """Get all holdings across all brokers"""
        holdings = db.query(Holding).all()
        return PortfolioService._serialize_holdings(db, holdings)

    @staticmethod
    def _serialize_holdings(db: Session, holdings: List[Holding]) -> List[HoldingResponse]:
        responses = []
        now = datetime.utcnow()
        for holding in holdings:
            latest_price = (
                db.query(Price)
                .filter(Price.asset_id == holding.asset_id)
                .order_by(Price.price_date.desc(), Price.id.desc())
                .first()
            )
            price_currency = (
                (latest_price.currency or holding.asset.currency or "EUR").upper()
                if latest_price is not None and holding.asset is not None
                else None
            )
            cost_currency = (
                (holding.asset.currency or "EUR").upper()
                if holding.asset is not None
                else None
            )
            compatible_currency = (
                price_currency is None
                or cost_currency is None
                or price_currency == cost_currency
            )
            gain_loss = (
                holding.current_value - holding.total_cost
                if (
                    holding.current_value is not None
                    and latest_price is not None
                    and compatible_currency
                )
                else None
            )
            gain_loss_percent = (
                float(gain_loss / holding.total_cost * 100)
                if gain_loss is not None and holding.total_cost > 0
                else None
            )
            age_days = (
                (now - latest_price.price_date).total_seconds() / 86400
                if latest_price is not None
                else None
            )
            responses.append(HoldingResponse(
                **{column.name: getattr(holding, column.name) for column in Holding.__table__.columns},
                asset=holding.asset,
                gain_loss=gain_loss,
                gain_loss_percent=gain_loss_percent,
                price_source=latest_price.source if latest_price else None,
                price_currency=price_currency,
                price_date=latest_price.price_date if latest_price else None,
                price_freshness=(
                    "fresh" if age_days is not None and age_days <= 3 else "stale"
                    if age_days is not None else "unavailable"
                ),
            ))
        return responses

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
        if summary.valuation_status in {"mixed_currency", "partial"}:
            raise ValueError(
                "Cannot create a complete portfolio snapshot while holdings "
                "have mixed currencies or missing prices"
            )
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


class EtoroPriceService:
    """Fetch USD market prices for portfolio holdings from eToro and store them."""

    SUPPORTED_ASSET_TYPES = {AssetType.STOCK, AssetType.ETF, AssetType.CRYPTO}

    def __init__(self, db: Session, client=None):
        self.db = db
        self.client = client

    @staticmethod
    def get_latest_portfolio_prices(db: Session) -> List[Dict]:
        """Return the newest stored market price for each asset."""
        latest_by_asset: Dict[str, Price] = {}
        for record in (
            db.query(Price)
            .order_by(Price.asset_id.asc(), Price.price_date.desc(), Price.id.desc())
            .all()
        ):
            latest_by_asset.setdefault(record.asset_id, record)

        return [
            {
                "symbol": record.asset_id,
                "currency": record.currency,
                "price": str(record.price),
                "price_date": record.price_date.isoformat(),
                "source": record.source,
                "freshness": (
                    "fresh"
                    if (datetime.utcnow() - record.price_date).total_seconds() <= 3 * 86400
                    else "stale"
                ),
            }
            for record in sorted(latest_by_asset.values(), key=lambda item: item.asset_id)
        ]

    async def sync_portfolio_prices(self) -> Dict:
        if self.client is None:
            return {
                "status": "error",
                "currency": "USD",
                "assets": 0,
                "prices_updated": 0,
                "errors": ["No eToro client provided"],
            }

        assets = (
            self.db.query(Asset)
            .join(Holding, Holding.asset_id == Asset.id)
            .filter(Holding.quantity > 0, Asset.asset_type.in_(list(self.SUPPORTED_ASSET_TYPES)))
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
        resolved_ids: Dict[str, int] = {}
        quote_map = {}
        updated_symbols = set()
        try:
            async with self.client as client:
                for asset in assets:
                    try:
                        instrument_id = await client.resolve_instrument_id(asset.symbol)
                        if instrument_id is not None:
                            resolved_ids[asset.symbol] = instrument_id
                        else:
                            errors.append(f"{asset.symbol}: no exact active instrument match")
                    except EtoroAPIError as exc:
                        errors.append(f"{asset.symbol}: {exc}")

                max_per_request = getattr(
                    client, "MAX_INSTRUMENTS_PER_REQUEST", 100
                )
                resolved_items = list(resolved_ids.items())
                for start in range(0, len(resolved_items), max_per_request):
                    chunk = resolved_items[start:start + max_per_request]
                    try:
                        quote_map.update(
                            await client.get_quotes(
                                [instrument_id for _, instrument_id in chunk]
                            )
                        )
                    except EtoroAPIError as exc:
                        errors.extend(
                            f"{symbol}: quote request failed: {exc}"
                            for symbol, _ in chunk
                        )

                for asset in assets:
                    instrument_id = resolved_ids.get(asset.symbol)
                    if instrument_id is None or instrument_id not in quote_map:
                        if instrument_id is not None and not any(
                            error.startswith(f"{asset.symbol}:")
                            for error in errors
                        ):
                            errors.append(f"{asset.symbol}: no valid quote available")
                        continue

                    quote = quote_map[instrument_id]
                    record = Price(
                        asset_id=asset.id,
                        price=quote.price_usd,
                        price_date=quote.price_date,
                        source="etoro",
                        currency="USD",
                    )
                    self.db.add(record)

                    for holding in self.db.query(Holding).filter(Holding.asset_id == asset.id).all():
                        if holding.quantity > 0:
                            holding.current_price = quote.price_usd
                            holding.current_value = (holding.quantity * quote.price_usd).quantize(Decimal("0.0001"))
                    updated_symbols.add(asset.symbol)
                self.db.commit()
        except Exception as exc:
            self.db.rollback()
            return {
                "status": "error",
                "currency": "USD",
                "assets": len(assets),
                "prices_updated": 0,
                "errors": [str(exc)],
            }

        return {
            "status": (
                "error" if errors and not updated_symbols
                else "partial" if errors
                else "success"
            ),
            "currency": "USD",
            "assets": len(assets),
            "prices_updated": len(updated_symbols),
            "errors": errors,
        }


class SECFundamentalsService:
    """Sync current portfolio holdings against SEC EDGAR company facts."""

    def __init__(self, db: Session, user_agent: str, transport: httpx.AsyncBaseTransport | None = None):
        self.db = db
        self.user_agent = user_agent or ""
        self.transport = transport

    async def sync_portfolio_facts(self) -> Dict:
        assets = (
            self.db.query(Asset)
            .join(Holding, Holding.asset_id == Asset.id)
            .filter(Holding.quantity > 0, Asset.asset_type.in_([AssetType.STOCK, AssetType.ETF]))
            .distinct()
            .order_by(Asset.symbol)
            .all()
        )

        if not self.user_agent or "@" not in self.user_agent:
            return {
                "status": "error",
                "symbols": len(assets),
                "facts_stored": 0,
                "facts_updated": 0,
                "errors": ["SEC_USER_AGENT must include a contact email"],
            }

        errors: List[str] = []
        facts_stored = 0
        facts_updated = 0

        try:
            headers = {
                "User-Agent": self.user_agent.strip(),
                "Accept-Encoding": "gzip, deflate",
            }
            async with httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                ticker_response = await client.get(SEC_TICKERS_URL)
                ticker_response.raise_for_status()
                ticker_map = build_ticker_map(ticker_response.json())

                for asset in assets:
                    cik = ticker_map.get(asset.symbol.upper())
                    if cik is None:
                        errors.append(f"{asset.symbol}: not found in SEC ticker map")
                        continue

                    try:
                        facts_response = await client.get(SEC_COMPANY_FACTS_URL.format(cik=cik))
                        facts_response.raise_for_status()
                        payload = facts_response.json()
                        if not isinstance(payload, dict):
                            raise ValueError("SEC Company Facts response was not an object")
                        selected = extract_company_facts(payload)
                    except (
                        httpx.HTTPError,
                        ValueError,
                        KeyError,
                        TypeError,
                        AttributeError,
                    ) as exc:
                        errors.append(f"{asset.symbol}: SEC facts request failed: {exc}")
                        continue

                    for fact in selected:
                        period_start = fact.get("period_start")
                        period_end = fact.get("period_end")
                        if period_end is None:
                            continue
                        existing = (
                            self.db.query(CompanyFinancialFact)
                            .filter(
                                CompanyFinancialFact.symbol == asset.symbol,
                                CompanyFinancialFact.metric == fact["metric"],
                                CompanyFinancialFact.period_end == period_end,
                                CompanyFinancialFact.units == fact["units"],
                            )
                            .order_by(
                                CompanyFinancialFact.filed_date.desc(),
                                CompanyFinancialFact.id.desc(),
                            )
                            .first()
                        )
                        if existing is not None:
                            if (
                                existing.accession_number != fact["accession_number"]
                                or existing.form != fact["form"]
                                or existing.value != Decimal(str(fact["value"]))
                            ):
                                existing.value = Decimal(str(fact["value"]))
                                existing.period_start = period_start
                                existing.filed_date = fact["filed_date"]
                                existing.form = fact["form"]
                                existing.accession_number = fact["accession_number"]
                                existing.fetched_at = datetime.utcnow()
                                facts_updated += 1
                            continue

                        record = CompanyFinancialFact(
                            symbol=asset.symbol,
                            metric=fact["metric"],
                            value=Decimal(str(fact["value"])),
                            units=fact["units"],
                            period_start=period_start,
                            period_end=period_end,
                            filed_date=fact["filed_date"],
                            form=fact["form"],
                            accession_number=fact["accession_number"],
                            source="SEC EDGAR",
                            fetched_at=datetime.utcnow(),
                        )
                        self.db.add(record)
                        facts_stored += 1

                self.db.commit()
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self.db.rollback()
            return {
                "status": "error",
                "symbols": len(assets),
                "facts_stored": facts_stored,
                "facts_updated": facts_updated,
                "errors": [str(exc)],
            }

        return {
            "status": "partial" if errors and (facts_stored or facts_updated) else
            "error" if errors else "success",
            "symbols": len(assets),
            "facts_stored": facts_stored,
            "facts_updated": facts_updated,
            "errors": errors,
        }


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
                    "message": "No observations returned for daily macro series",
                    "series_without_observations": list(data),
                }
            count = self._store_macro_data(data)
            logger.info(f"Successfully stored {count} daily macro records")
            empty_series = [series_id for series_id, observations in data.items() if not observations]
            return {
                "status": "partial" if empty_series else "success",
                "records_stored": count,
                "series": list(data.keys()),
                "series_without_observations": empty_series,
            }
        except Exception as e:
            self.db.rollback()
            logger.exception("Error fetching daily macro data")
            return {"status": "error", "message": str(e)}

    def fetch_and_store_monthly_macro(self, start_date: Optional[str] = None) -> Dict:
        """Fetch and store monthly macro data (CPI)"""
        try:
            logger.info("Starting monthly macro data fetch...")
            data = self.fred.fetch_monthly_series(start_date)
            if not any(data.values()):
                return {
                    "status": "error",
                    "message": "No observations returned for monthly macro series",
                    "series_without_observations": list(data),
                }
            count = self._store_macro_data(data)
            logger.info(f"Successfully stored {count} monthly macro records")
            empty_series = [series_id for series_id, observations in data.items() if not observations]
            return {
                "status": "partial" if empty_series else "success",
                "records_stored": count,
                "series": list(data.keys()),
                "series_without_observations": empty_series,
            }
        except Exception as e:
            self.db.rollback()
            logger.exception("Error fetching monthly macro data")
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

                if existing is None:
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
                elif existing.value != value or existing.units != units:
                    existing.value = value
                    existing.units = units
                    existing.fetched_at = datetime.utcnow()

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
        symbols = sorted(set(h.asset_id for h in holdings))
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

            all_news = {}
            fetch_errors = []
            successful_fetches = 0
            for symbol in symbols:
                try:
                    all_news.update(
                        await fetch_news_for_stocks([symbol], days=days)
                    )
                    successful_fetches += 1
                except RuntimeError as exc:
                    fetch_errors.append(f"{symbol}: {exc}")

            total_stored = 0
            for symbol, articles in all_news.items():
                stored = NewsService._store_articles(db, symbol, articles)
                total_stored += stored
                logger.info(f"Stored {stored} new articles for {symbol}")

            logger.info(f"Total articles stored: {total_stored}")
            return {
                "status": (
                    "error" if fetch_errors and successful_fetches == 0
                    else "partial" if fetch_errors
                    else "success"
                ),
                "symbols": len(symbols),
                "articles_stored": total_stored,
                "symbols_list": symbols,
                "errors": fetch_errors,
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
                    published_date=article.published_date,
                    fetched_at=datetime.utcnow(),
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
