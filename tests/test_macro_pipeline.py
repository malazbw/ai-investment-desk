from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data_sources.fred import FREDFetcher
from app.models import Base, MacroIndicator
from app.services import MacroDataService


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return engine, session


def test_storing_same_macro_observations_twice_does_not_duplicate_rows():
    engine, db = make_session()
    service = MacroDataService(db, "test-key")
    observations = {
        "DFF": [
            ("2026-10-30", Decimal("3.25")),
            ("2026-10-31", Decimal("3.50")),
        ]
    }

    try:
        assert service._store_macro_data(observations) == 2
        assert service._store_macro_data(observations) == 0
        assert db.query(MacroIndicator).count() == 2
        assert db.query(MacroIndicator).filter(
            MacroIndicator.date == datetime(2026, 10, 30)
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_fetch_series_uses_fred_observations_endpoint():
    response = Mock()
    response.json.return_value = {
        "observations": [{"date": "2026-10-31", "value": "3.50"}]
    }
    fetcher = FREDFetcher("test-key")

    with patch("app.data_sources.fred.requests.get", return_value=response) as get:
        observations = fetcher.fetch_series("DFF", start_date="2026-10-01")

    assert observations == [("2026-10-31", Decimal("3.50"))]
    get.assert_called_once_with(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": "DFF",
            "api_key": "test-key",
            "observation_start": "2026-10-01",
            "file_type": "json",
        },
        timeout=10,
    )


def test_daily_macro_fetch_passes_backfill_start_date_to_fetcher():
    engine, db = make_session()
    service = MacroDataService(db, "test-key")
    start_date = "2023-11-02"

    try:
        with patch.object(service.fred, "fetch_daily_series", return_value={}) as fetch:
            result = service.fetch_and_store_daily_macro(start_date)

        assert result["status"] == "success"
        fetch.assert_called_once_with(start_date)
    finally:
        db.close()
        engine.dispose()


def test_monthly_macro_fetch_passes_backfill_start_date_to_fetcher():
    engine, db = make_session()
    service = MacroDataService(db, "test-key")
    start_date = "2023-11-02"

    try:
        with patch.object(service.fred, "fetch_monthly_series", return_value={}) as fetch:
            result = service.fetch_and_store_monthly_macro(start_date)

        assert result["status"] == "success"
        fetch.assert_called_once_with(start_date)
    finally:
        db.close()
        engine.dispose()
