from datetime import datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.brokers.etoro import EtoroMarketDataClient, EtoroQuote
from app.models import Asset, AssetType, Base, BrokerType, Holding, Price
from app.services import EtoroPriceService


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return engine, session


@pytest.mark.asyncio
async def test_client_resolves_exact_symbol_and_normalizes_quote_to_usd():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "public-key"
        assert request.headers["x-user-key"] == "user-key"
        assert request.headers.get("x-request-id")
        if request.url.path.endswith("/search"):
            assert request.url.params["internalSymbolFull"] == "ABC"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"instrumentId": 10, "internalSymbolFull": "ABC.L"},
                        {"instrumentId": 11, "internalSymbolFull": "ABC"},
                    ]
                },
            )
        assert request.url.path.endswith("/instruments/rates")
        assert request.url.params["instrumentIds"] == "11"
        return httpx.Response(
            200,
            json={
                "rates": [
                    {
                        "instrumentID": 11,
                        "lastExecution": 25,
                        "bid": 24,
                        "ask": 26,
                        "conversionRateBid": 1.1,
                        "conversionRateAsk": 1.2,
                        "date": "2026-11-04T15:00:00Z",
                    }
                ]
            },
        )

    client = EtoroMarketDataClient(
        "public-key",
        "user-key",
        transport=httpx.MockTransport(handler),
    )
    async with client:
        instrument_id = await client.resolve_instrument_id("ABC")
        quotes = await client.get_quotes([instrument_id])

    assert instrument_id == 11
    assert quotes[11] == EtoroQuote(
        instrument_id=11,
        price_usd=Decimal("28.75"),
        price_date=datetime(2026, 11, 4, 15, 0),
    )


@pytest.mark.asyncio
async def test_client_ignores_delisted_and_rejects_missing_usd_conversion():
    responses = [
        httpx.Response(
            200,
            json={
                "items": [
                    {
                        "instrumentId": 12,
                        "internalSymbolFull": "XYZ",
                        "isDelisted": True,
                    }
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "rates": [
                    {
                        "instrumentID": 12,
                        "lastExecution": 10,
                        "date": "2026-11-04T15:00:00Z",
                    }
                ]
            },
        ),
    ]
    client = EtoroMarketDataClient(
        "public-key",
        "user-key",
        transport=httpx.MockTransport(lambda request: responses.pop(0)),
    )
    async with client:
        assert await client.resolve_instrument_id("XYZ") is None
        assert await client.get_quotes([12]) == {}


class FakeEtoroClient:
    MAX_INSTRUMENTS_PER_REQUEST = 100

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def resolve_instrument_id(self, symbol):
        return {"AAPL": 1, "BTC": 2}.get(symbol)

    async def get_quotes(self, instrument_ids):
        return {
            instrument_id: EtoroQuote(
                instrument_id=instrument_id,
                price_usd=Decimal("123.12345678"),
                price_date=datetime(2026, 11, 4, 15, 0),
            )
            for instrument_id in instrument_ids
        }


@pytest.mark.asyncio
async def test_service_stores_supported_asset_prices_in_usd_and_updates_holdings():
    engine, db = make_session()
    try:
        for symbol, asset_type in (
            ("AAPL", AssetType.STOCK),
            ("BTC", AssetType.CRYPTO),
            ("BND", AssetType.COMMODITY),
        ):
            asset = Asset(
                id=symbol,
                symbol=symbol,
                name=symbol,
                asset_type=asset_type,
            )
            db.add(asset)
            db.flush()
            db.add(
                Holding(
                    asset_id=symbol,
                    broker=BrokerType.BINANCE,
                    quantity=Decimal("2"),
                    average_cost=Decimal("100"),
                    total_cost=Decimal("200"),
                )
            )
        db.commit()

        result = await EtoroPriceService(db, FakeEtoroClient()).sync_portfolio_prices()

        assert result["status"] == "success"
        assert result["assets"] == 2
        assert result["prices_updated"] == 2
        records = db.query(Price).order_by(Price.asset_id).all()
        assert [(record.asset_id, record.currency) for record in records] == [
            ("AAPL", "USD"),
            ("BTC", "USD"),
        ]
        assert all(record.price == Decimal("123.12345678") for record in records)
        assert all(record.source == "etoro" for record in records)
        assert db.query(Holding).filter(Holding.asset_id == "AAPL").one().current_value == Decimal("246.2469")
        latest = EtoroPriceService.get_latest_portfolio_prices(db)
        assert [price["currency"] for price in latest] == ["USD", "USD"]

        standalone = Asset(
            id="QQQ",
            symbol="QQQ",
            name="QQQ",
            asset_type=AssetType.ETF,
            currency="USD",
        )
        db.add(standalone)
        db.flush()
        db.add(
            Price(
                asset_id="QQQ",
                price=Decimal("500"),
                price_date=datetime(2026, 11, 4, 15, 0),
                source="etoro",
                currency="USD",
            )
        )
        db.commit()
        latest = EtoroPriceService.get_latest_portfolio_prices(db)
        assert [price["symbol"] for price in latest] == ["AAPL", "BTC", "QQQ"]
    finally:
        db.close()
        engine.dispose()
