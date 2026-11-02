from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data_sources.frankfurter import FrankfurterFetcher
from app.models import Base, ExchangeRate
from app.services import ExchangeRateService


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return engine, session


def test_fetcher_requests_eur_reference_rates_and_parses_response():
    response = Mock()
    response.json.return_value = [
        {"date": "2026-10-30", "base": "EUR", "quote": "USD", "rate": 1.16},
        {"date": "2026-10-30", "base": "EUR", "quote": "GBP", "rate": 0.87},
    ]
    fetcher = FrankfurterFetcher()

    with patch("app.data_sources.frankfurter.requests.get", return_value=response) as get:
        rates = fetcher.fetch_rates("2026-10-30")

    assert rates == [
        (date(2026, 10, 30), "EUR", "USD", Decimal("1.16")),
        (date(2026, 10, 30), "EUR", "GBP", Decimal("0.87")),
    ]
    get.assert_called_once_with(
        "https://api.frankfurter.dev/v2/rates",
        params={
            "from": "2026-10-30",
            "base": "EUR",
            "quotes": "USD,GBP,CHF",
        },
        timeout=30,
    )


def test_exchange_rate_ingestion_is_idempotent_and_updates_revisions():
    engine, db = make_session()
    service = ExchangeRateService(db)
    observation = (date(2026, 10, 30), "EUR", "USD", Decimal("1.16"))

    try:
        with patch.object(service.fetcher, "fetch_rates", return_value=[observation]):
            first = service.fetch_and_store_daily_rates("2026-10-30")
            second = service.fetch_and_store_daily_rates("2026-10-30")

        assert first["records_inserted"] == 1
        assert second["records_inserted"] == 0
        assert db.query(ExchangeRate).count() == 1

        revised_observation = (*observation[:3], Decimal("1.17"))
        with patch.object(service.fetcher, "fetch_rates", return_value=[revised_observation]):
            revised = service.fetch_and_store_daily_rates("2026-10-30")

        assert revised["records_updated"] == 1
        assert db.query(ExchangeRate).one().rate == Decimal("1.17")
    finally:
        db.close()
        engine.dispose()
