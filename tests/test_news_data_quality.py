from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data_sources.news_fetcher import NewsArticle
from app.models import Asset, AssetType, Base, BrokerType, CompanyNews, Holding
from app.services import NewsService


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_news_sync_keeps_successful_symbols_when_another_provider_request_fails(
    monkeypatch,
):
    engine, db = make_session()
    try:
        for symbol in ("AAPL", "MSFT"):
            db.add(Asset(
                id=symbol,
                symbol=symbol,
                name=symbol,
                asset_type=AssetType.STOCK,
            ))
            db.flush()
            db.add(Holding(
                asset_id=symbol,
                broker=BrokerType.SCALABLE_CAPITAL,
                quantity=Decimal("1"),
                average_cost=Decimal("10"),
                total_cost=Decimal("10"),
            ))
        db.commit()

        async def fetch_for_symbols(symbols, days):
            symbol = symbols[0]
            if symbol == "MSFT":
                raise RuntimeError("provider unavailable")
            return {
                symbol: [
                    NewsArticle(
                        symbol=symbol,
                        headline="Apple reports quarterly results",
                        url="https://example.test/aapl-results",
                        source="Example News",
                        published_date=datetime(2026, 11, 5),
                        description="Publisher-provided summary.",
                    )
                ]
            }

        monkeypatch.setattr(
            "app.data_sources.news_fetcher.fetch_news_for_stocks",
            fetch_for_symbols,
        )
        result = await NewsService.fetch_and_store_portfolio_news(db)

        assert result["status"] == "partial"
        assert result["articles_stored"] == 1
        assert result["errors"] == ["MSFT: provider unavailable"]
        stored = db.query(CompanyNews).one()
        assert stored.description == "Publisher-provided summary."
        assert NewsService.get_portfolio_news(db, days=30)["AAPL"][0]["description"] == (
            "Publisher-provided summary."
        )
    finally:
        db.close()
        engine.dispose()
