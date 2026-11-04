from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from app.agents.tools.company_research import CompanyResearchTool
from app.data_sources.news_fetcher import NewsArticle


def sec_company_facts():
    annual_fields = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": (
            "USD",
            1000,
            True,
        ),
        "NetIncomeLoss": ("USD", 250, True),
        "EarningsPerShareDiluted": ("USD/shares", 5, True),
    }
    facts = {}
    for tag, (unit, value, duration) in annual_fields.items():
        observations = []
        for year, fact_value in ((2025, value), (2024, value * 4 // 5)):
            observation = {
                "end": f"{year}-12-31",
                "filed": f"{year + 1}-02-20",
                "form": "10-K",
                "accn": f"0000000000-{year + 1}-000001",
                "val": fact_value,
            }
            if duration:
                observation.update(
                    {
                        "start": f"{year}-01-01",
                        "fp": "FY",
                    }
                )
            observations.append(observation)
        facts[tag] = {"units": {unit: observations}}
    return {"facts": {"us-gaap": facts}}


class FakeEtoroClient:
    def __init__(self, **kwargs):
        self.instrument_ids = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def resolve_instrument_id(self, symbol):
        assert symbol == "NVDA"
        return 42

    async def get_quotes(self, instrument_ids):
        self.instrument_ids.extend(instrument_ids)
        return {
            42: SimpleNamespace(
                price_usd=Decimal("150"),
                price_date=datetime(2026, 11, 3),
            )
        }


@pytest.mark.asyncio
async def test_on_demand_research_combines_sources_without_portfolio_records():
    requests = []

    async def sec_handler(request):
        requests.append(request)
        if request.url.path == "/files/company_tickers.json":
            return httpx.Response(
                200,
                json={
                    "0": {
                        "cik_str": 1045810,
                        "ticker": "NVDA",
                        "title": "NVIDIA Corp",
                    }
                },
            )
        return httpx.Response(200, json=sec_company_facts())

    async def news_search(query, days):
        assert query == '"NVIDIA" OR NVDA'
        assert days == 30
        return [
            NewsArticle(
                symbol="NVDA",
                headline="NVIDIA reports results",
                url="https://example.test/nvda",
                source="Example News",
                published_date=datetime(2026, 11, 3),
                description="Publisher summary only.",
            )
        ]

    tool = CompanyResearchTool(
        user_agent="AI Investment Desk contact: test@example.com",
        etoro_api_key="test-key",
        etoro_user_key="test-user-key",
        newsapi_key="test-news-key",
        sec_transport=httpx.MockTransport(sec_handler),
        etoro_client_factory=FakeEtoroClient,
        news_search=news_search,
    )

    result = await tool.research("NVDA")

    assert result["company_name"] == "NVIDIA Corp"
    assert result["sources"]["sec"]["status"] == "available"
    assert result["sources"]["market_price"] == {
        "status": "available",
        "price": "150",
        "currency": "USD",
        "date": "2026-11-03T00:00:00",
        "source": "eToro",
    }
    assert result["sources"]["news"]["evidence_level"] == (
        "headline_and_publisher_snippet"
    )
    assert result["valuation"]["pe_ratio"] == "30"
    assert result["valuation"]["net_profit_margin_percent"] == "25.00"
    assert result["valuation"]["year_over_year_growth"]["revenue"]["percent"] == "25.00"
    assert result["valuation"]["year_over_year_growth"]["diluted_eps"]["percent"] == "25.00"
    revenue_analysis = result["fundamental_analysis"]["findings"][0]
    assert revenue_analysis["metric"] == "revenue_growth"
    assert "25.0%" in revenue_analysis["finding"]
    assert "not a forecast" in revenue_analysis["meaning"]
    assert result["fundamental_analysis"]["valuation_interpretation"][
        "counterpoint"
    ].startswith("A trailing P/E does not establish fair value")
    assert all(
        request.headers["user-agent"]
        == "AI Investment Desk contact: test@example.com"
        for request in requests
    )


@pytest.mark.asyncio
async def test_on_demand_research_reports_unconfigured_sources_explicitly():
    tool = CompanyResearchTool(
        user_agent="",
        etoro_api_key="",
        etoro_user_key="",
        newsapi_key="",
    )

    result = await tool.research("NVDA")

    assert result["sources"]["sec"]["status"] == "unavailable"
    assert result["sources"]["market_price"]["status"] == "unavailable"
    assert result["sources"]["news"]["status"] == "unavailable"
    assert result["valuation"]["pe_ratio"] is None
