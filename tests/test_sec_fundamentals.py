from datetime import date, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import AgentContext, ValuationAgent
from app.data_sources.sec import (
    build_ticker_map,
    extract_annual_fact_history,
    extract_company_facts,
)
from app.models import Asset, AssetType, Base, BrokerType, Holding, Price
from app.services import SECFundamentalsService


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def company_facts_payload():
    annual = {
        "start": "2024-09-29",
        "end": "2025-09-27",
        "filed": "2025-10-30",
        "form": "10-K",
        "fp": "FY",
        "accn": "0000320193-25-000100",
        "val": 1000,
    }

    def tagged_fact(unit, value, *, duration=False):
        observation = {**annual, "val": value}
        if not duration:
            observation.pop("start")
            observation.pop("fp")
        return {"units": {unit: [observation]}}

    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax":
                    tagged_fact("USD", 1000, duration=True),
                "NetIncomeLoss": tagged_fact("USD", 100, duration=True),
                "EarningsPerShareDiluted":
                    tagged_fact("USD/shares", 5, duration=True),
                "NetCashProvidedByUsedInOperatingActivities":
                    tagged_fact("USD", 200, duration=True),
                "PaymentsToAcquirePropertyPlantAndEquipment":
                    tagged_fact("USD", 50, duration=True),
                "Assets": tagged_fact("USD", 2000),
                "Liabilities": tagged_fact("USD", 1000),
                "StockholdersEquity": tagged_fact("USD", 1000),
            }
        }
    }


def test_sec_fact_parser_selects_reported_annual_facts_and_ticker_cik():
    ticker_map = build_ticker_map(
        {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    )
    assert ticker_map == {"AAPL": "0000320193"}

    facts = extract_company_facts(
        company_facts_payload(),
        current_date=date(2026, 11, 4),
    )
    assert len(facts) == 8
    revenue = next(fact for fact in facts if fact["metric"] == "revenue")
    assert revenue["value"] == "1000"
    assert revenue["period_start"] == date(2024, 9, 29)
    assert revenue["period_end"] == date(2025, 9, 27)
    assert revenue["filed_date"] == date(2025, 10, 30)


def test_sec_fact_parser_selects_latest_fact_across_alternate_gaap_tags():
    old_tag = {
        "units": {
            "USD": [
                {
                    "start": "2022-01-01",
                    "end": "2022-12-31",
                    "filed": "2023-02-01",
                    "form": "10-K",
                    "fp": "FY",
                    "accn": "old-accession",
                    "val": 100,
                }
            ]
        }
    }
    new_tag = {
        "units": {
            "USD": [
                {
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                    "filed": "2025-02-01",
                    "form": "10-K",
                    "fp": "FY",
                    "accn": "new-accession",
                    "val": 300,
                }
            ]
        }
    }
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": old_tag,
                "SalesRevenueNet": new_tag,
            }
        }
    }

    facts = extract_company_facts(
        payload,
        current_date=date(2026, 11, 4),
    )

    assert len(facts) == 1
    assert facts[0]["metric"] == "revenue"
    assert facts[0]["value"] == "300"
    assert facts[0]["accession_number"] == "new-accession"


def test_annual_history_keeps_multiple_periods_from_the_same_filing():
    observations = [
        {
            "start": "2023-01-01",
            "end": "2023-12-31",
            "filed": "2025-02-01",
            "form": "10-K",
            "fp": "FY",
            "accn": "same-accession",
            "val": 100,
        },
        {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "filed": "2025-02-01",
            "form": "10-K",
            "fp": "FY",
            "accn": "same-accession",
            "val": 200,
        },
        {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "filed": "2026-02-01",
            "form": "10-K",
            "fp": "FY",
            "accn": "amended-accession",
            "val": 250,
        },
    ]
    payload = {
        "facts": {
            "us-gaap": {
                "SalesRevenueNet": {"units": {"USD": observations}},
            }
        }
    }

    history = extract_annual_fact_history(
        payload,
        current_date=date(2026, 11, 4),
    )

    assert [
        (fact["value"], fact["period_end"].isoformat())
        for fact in history["revenue"]
    ] == [("250", "2024-12-31"), ("100", "2023-12-31")]


@pytest.mark.asyncio
async def test_sec_sync_stores_facts_and_valuation_agent_calculates_metrics():
    engine, db = make_session()
    requests = []
    try:
        db.add(
            Asset(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_type=AssetType.STOCK,
                currency="USD",
            )
        )
        db.flush()
        db.add(
            Holding(
                asset_id="AAPL",
                broker=BrokerType.SCALABLE_CAPITAL,
                quantity=Decimal("10"),
                average_cost=Decimal("40"),
                total_cost=Decimal("400"),
                current_price=Decimal("50"),
                current_value=Decimal("500"),
            )
        )
        db.add(
            Price(
                asset_id="AAPL",
                price=Decimal("50"),
                price_date=datetime(2026, 11, 4),
                source="test",
                currency="USD",
            )
        )
        db.commit()

        def handler(request):
            requests.append(request)
            if request.url.path == "/files/company_tickers.json":
                return httpx.Response(
                    200,
                    json={
                        "0": {
                            "cik_str": 320193,
                            "ticker": "AAPL",
                            "title": "Apple Inc.",
                        }
                    },
                )
            return httpx.Response(200, json=company_facts_payload())

        result = await SECFundamentalsService(
            db,
            "AI Investment Desk contact: test@example.com",
            transport=httpx.MockTransport(handler),
        ).sync_portfolio_facts()

        assert result == {
            "status": "success",
            "symbols": 1,
            "facts_stored": 8,
            "facts_updated": 0,
            "errors": [],
        }
        assert requests[0].headers["user-agent"] == (
            "AI Investment Desk contact: test@example.com"
        )

        output = await ValuationAgent().execute(
            AgentContext(user_message="Value AAPL", metadata={"db": db})
        )
        apple = output.data["assets"][0]
        assert output.success
        assert apple["fundamentals_status"] == "available"
        assert Decimal(apple["pe_ratio"]) == Decimal("10")
        assert Decimal(apple["net_profit_margin_percent"]) == Decimal("10")
        assert Decimal(apple["free_cash_flow"]) == Decimal("150")
        assert apple["revenue"]["source"] == "SEC EDGAR"
        assert apple["revenue"]["period_end"] == "2025-09-27"
    finally:
        db.close()
        engine.dispose()
