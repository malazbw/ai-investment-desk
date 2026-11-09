import asyncio
import json
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import (
    AgentContext,
    AgentRouter,
    MacroContextAgent,
    MarketResearchAgent,
    RiskManagerAgent,
    SynthesisAgent,
    ValuationAgent,
    execute_agents_parallel,
)
from app.agents.assistant_workflow import AssistantWorkflow
from app.agents.tools import CompanyResearchTool, extract_company_symbols
from app.agents.base import AgentOutput, BaseAgent
from app.agents.portfolio_agent import PortfolioAgent
from app.chat_schemas import ChatMessage
from app.llm.client import LLMClient
from app.llm.providers import GeminiProvider, LLMFactory
from app.data_sources.news_fetcher import NewsArticle
from app.models import (
    Asset,
    AssetType,
    Base,
    BrokerType,
    CompanyNews,
    Holding,
    MacroIndicator,
    Price,
)
from app.routes import chat_message, sync_virtual_broker
from app.services import NewsService


class StubProvider:
    def __init__(self, route_response='["portfolio"]'):
        self.calls = []
        self.route_response = route_response

    async def analyze(self, user_message, system_prompt, context):
        self.calls.append(
            {
                "user_message": user_message,
                "system_prompt": system_prompt,
                "context": context,
            }
        )
        if "Select only the specialists needed" in system_prompt:
            return self.route_response
        return "Combined assessment."


@pytest.mark.asyncio
async def test_gemini_provider_sends_prompt_and_parses_response():
    import httpx

    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Portfolio assessment."}]}}
                ]
            },
        )

    provider = GeminiProvider(api_key="test-key")
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        answer = await provider.analyze(
            "How is my portfolio?",
            "Be concise.",
            {"portfolio": {"value": "100"}},
        )
    finally:
        await provider.client.aclose()

    assert answer == "Portfolio assessment."
    assert requests[0].headers["x-goog-api-key"] == "test-key"
    assert requests[0].url.path.endswith(
        "/models/gemini-3.5-flash-lite:generateContent"
    )
    payload = json.loads(requests[0].content)
    assert payload["systemInstruction"]["parts"][0]["text"] == "Be concise."
    assert "value: 100" in payload["contents"][0]["parts"][0]["text"]
    assert payload["generationConfig"]["maxOutputTokens"] == 2048
    factory_provider = LLMFactory.create_provider("gemini", api_key="test-key")
    assert factory_provider.model == "gemini-3.5-flash-lite"
    await factory_provider.client.aclose()


@pytest.mark.asyncio
async def test_gemini_provider_rejects_truncated_output():
    import httpx

    async def handler(request):
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "MAX_TOKENS",
                        "content": {"parts": [{"text": "Incomplete response"}]},
                    }
                ]
            },
        )

    provider = GeminiProvider(api_key="test-key")
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(RuntimeError, match="output token limit"):
            await provider.analyze("Question", "Prompt", {})
    finally:
        await provider.client.aclose()


def make_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(autoflush=False, bind=engine)


def seed_portfolio(db):
    asset = Asset(
        id="AAPL",
        symbol="AAPL",
        name="Apple",
        asset_type=AssetType.STOCK,
        currency="USD",
    )
    db.add(asset)
    db.flush()
    db.add(
        Holding(
            asset_id=asset.id,
            broker=BrokerType.BINANCE,
            quantity=Decimal("2"),
            average_cost=Decimal("100"),
            total_cost=Decimal("200"),
            current_price=Decimal("110"),
            current_value=Decimal("220"),
        )
    )
    db.add(
        Price(
            asset_id=asset.id,
            price=Decimal("110"),
            price_date=datetime(2026, 11, 4),
            source="etoro",
            currency="USD",
        )
    )
    db.commit()
    return asset


@pytest.mark.asyncio
async def test_router_selects_only_the_specialists_returned_by_intent_classifier():
    agents = {
        "portfolio": PortfolioAgent(),
        "market_research": MarketResearchAgent(),
        "macro": MacroContextAgent(),
        "risk": RiskManagerAgent(),
        "valuation": ValuationAgent(),
    }
    provider = StubProvider(route_response='["portfolio", "risk"]')

    selected = await AgentRouter(agents).decide_agents(
        "Should I buy Apple?", LLMClient(provider)
    )

    assert [agent.name for agent in selected] == ["portfolio", "risk"]
    assert "Select only the specialists needed" in provider.calls[0]["system_prompt"]


@pytest.mark.asyncio
async def test_router_accepts_portfolio_only_classification_for_holdings_question():
    agents = {
        "portfolio": PortfolioAgent(),
        "market_research": MarketResearchAgent(),
        "macro": MacroContextAgent(),
        "risk": RiskManagerAgent(),
        "valuation": ValuationAgent(),
    }
    provider = StubProvider(route_response='["portfolio"]')

    selected = await AgentRouter(agents).decide_agents(
        "Which holdings do I have?", LLMClient(provider)
    )

    assert [agent.name for agent in selected] == ["portfolio"]


@pytest.mark.asyncio
async def test_router_rejects_unknown_specialists_from_classifier():
    agents = {
        "portfolio": PortfolioAgent(),
        "market_research": MarketResearchAgent(),
        "macro": MacroContextAgent(),
        "risk": RiskManagerAgent(),
        "valuation": ValuationAgent(),
    }
    provider = StubProvider(route_response='["portfolio", "unknown"]')

    with pytest.raises(ValueError, match="invalid specialist names"):
        await AgentRouter(agents).decide_agents(
            "What is the P/E and valuation?", LLMClient(provider)
        )

    assert extract_company_symbols("Should I invest in NVIDIA?") == ["NVDA"]


def test_direct_portfolio_answer_labels_partial_valuation_and_price_provenance():
    response = AssistantWorkflow._answer_portfolio_lookup(
        {
            "agent_outputs": [
                AgentOutput(
                    agent_name="portfolio",
                    success=True,
                    data={
                        "portfolio_summary": {
                            "total_value": "120",
                            "currency": "USD",
                            "valuation_status": "partial",
                            "unpriced_holdings": ["MSFT"],
                        },
                        "holdings": [
                            {
                                "symbol": "AAPL",
                                "quantity": "1.00000000",
                                "price_source": "virtual_broker",
                                "price_date": "2026-11-04T12:00:00",
                            },
                            {"symbol": "MSFT", "quantity": "2"},
                        ],
                    },
                )
            ]
        }
    )["response"]

    assert "Partial stored value: USD 120.00." in response
    assert "No usable stored price for: MSFT." in response
    assert "Virtual broker prices are sample data, not live quotes" in response
    assert "observed 2026-11-04" in response


@pytest.mark.asyncio
async def test_research_valuation_risk_and_macro_agents_return_dated_data():
    engine, session_factory = make_session_factory()
    db = session_factory()
    try:
        asset = seed_portfolio(db)
        db.add(
            CompanyNews(
                symbol=asset.id,
                headline="Apple reports quarterly earnings",
                url="https://example.test/aapl-earnings",
                source="Example Financial News",
                published_date=datetime(2026, 11, 4),
            )
        )
        db.add(
            MacroIndicator(
                series_id="VIXCLS",
                date=datetime(2026, 11, 4),
                value=Decimal("18.2"),
                units="index",
                source="FRED",
            )
        )
        db.commit()
        context = AgentContext(user_message="Analyze Apple.", metadata={"db": db})

        research, portfolio, valuation, risk, macro = await asyncio.gather(
            MarketResearchAgent().execute(context),
            PortfolioAgent().execute(context),
            ValuationAgent().execute(context),
            RiskManagerAgent().execute(context),
            MacroContextAgent().execute(context),
        )

        assert research.success
        assert research.data["articles"][0]["symbol"] == "AAPL"
        assert research.data["articles"][0]["url"] == "https://example.test/aapl-earnings"
        assert set(research.data["assessment"]) == {
            "finding", "evidence", "meaning", "counterpoint", "confidence", "missing"
        }

        assert portfolio.success
        assert portfolio.data["holdings"][0]["price_source"] == "etoro"
        assert "stored in this desk" in portfolio.data["assessment"]["meaning"].lower()

        assert valuation.success
        assert valuation.data["assets"][0]["pe_ratio"] is None
        assert valuation.data["status"] == "fundamentals_unavailable"
        assert valuation.data["assessment"]["missing"]

        assert risk.success
        assert risk.data["largest_positions"][0]["symbol"] == "AAPL"
        assert Decimal(risk.data["largest_positions"][0]["weight_percent"]) == Decimal("100")
        assert "USD" in risk.data["assessment"]["evidence"][0]

        assert macro.success
        assert macro.data["indicators"]["VIXCLS"]["value"] == "18.2000"
        assert macro.data["indicators"]["VIXCLS"]["source"] == "FRED"
        assert macro.data["assessment"]["evidence"][0].startswith("VIX Index:")
        assert "do not establish an economic regime" in macro.data["assessment"][
            "meaning"
        ]
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_market_research_agent_calls_tool_for_unheld_company_only():
    engine, session_factory = make_session_factory()
    db = session_factory()

    class FakeCompanyResearchTool:
        def __init__(self):
            self.symbols = []

        async def research(self, symbol):
            self.symbols.append(symbol)
            return {
                "symbol": symbol,
                "fundamental_analysis": {
                    "findings": [{"metric": "revenue_growth"}]
                },
                "sources": {
                    "sec": {"status": "available"},
                    "market_price": {"status": "available"},
                    "news": {"status": "available"},
                },
                "valuation": {"pe_ratio": "32.5"},
            }

    tool = FakeCompanyResearchTool()
    llm_calls = []

    class NewsLLM:
        async def analyze(self, user_message, system_prompt, context):
            llm_calls.append(
                {
                    "user_message": user_message,
                    "system_prompt": system_prompt,
                    "context": context,
                }
            )
            return "Revenue growth is positive historical evidence, not a forecast."

    try:
        seed_portfolio(db)
        output = await MarketResearchAgent(tool).execute(
            AgentContext(
                user_message="Should I invest in NVIDIA?",
                metadata={"db": db, "llm_client": NewsLLM()},
            )
        )

        assert output.success
        assert tool.symbols == ["NVDA"]
        assert output.data["on_demand_research"][0]["valuation"]["pe_ratio"] == "32.5"
        assert output.data["on_demand_analysis"].startswith("Revenue growth")
        assert llm_calls[0]["context"]["on_demand_company_research"][0][
            "fundamental_findings"
        ][0]["metric"] == "revenue_growth"
        assert "do not invent business drivers" in llm_calls[0][
            "system_prompt"
        ].lower()
        assert "NVDA" in output.data["assessment"]["finding"]
        assert "separate from stored portfolio holdings" in output.data["assessment"][
            "meaning"
        ]
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_detailed_company_research_includes_requested_portfolio_company():
    engine, session_factory = make_session_factory()
    db = session_factory()
    llm_calls = []

    class FakeCompanyResearchTool:
        def __init__(self):
            self.symbols = []

        async def research(self, symbol):
            self.symbols.append(symbol)
            return {
                "symbol": symbol,
                "sources": {
                    "sec": {
                        "status": "available",
                        "annual_history": {"revenue": [{"value": "1000"}]},
                    },
                    "market_price": {"status": "available"},
                    "news": {"status": "available"},
                },
                "valuation": {
                    "latest_annual_facts": {
                        "total_assets": {"value": "5000", "units": "USD"}
                    }
                },
                "fundamental_analysis": {"findings": []},
            }

    class NewsLLM:
        async def analyze(self, user_message, system_prompt, context):
            llm_calls.append(
                {
                    "user_message": user_message,
                    "system_prompt": system_prompt,
                    "context": context,
                }
            )
            return "Structured company research report."

    try:
        apple = seed_portfolio(db)
        db.add(
            CompanyNews(
                symbol=apple.id,
                headline="Apple earnings update",
                url="https://example.test/aapl",
                source="Example Finance",
                published_date=datetime(2026, 11, 4),
            )
        )
        db.commit()
        tool = FakeCompanyResearchTool()

        output = await MarketResearchAgent(tool).execute(
            AgentContext(
                user_message=(
                    "Prepare a company profile for Apple covering products and how "
                    "they build them, challenges, plans, value chain, competitors, "
                    "competitive advantages, and financial statements."
                ),
                metadata={"db": db, "llm_client": NewsLLM()},
            )
        )

        assert output.success
        assert tool.symbols == ["AAPL"]
        assert "Products and how the company makes or delivers them" in llm_calls[0][
            "system_prompt"
        ]
        assert "do not invent products" in llm_calls[0]["system_prompt"].lower()
        assert "under 450 words" in llm_calls[0]["system_prompt"]
        assert llm_calls[0]["context"]["stored_portfolio_news"] == {}
        assert "under 450 words" in llm_calls[0]["user_message"]
        company_context = llm_calls[0]["context"]["on_demand_company_research"][0]
        assert company_context["latest_annual_facts"]["total_assets"]["value"] == "5000"
        assert company_context["annual_history"]["revenue"][0]["value"] == "1000"
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_market_research_filters_ticker_noise_and_caveats_headline_analysis():
    engine, session_factory = make_session_factory()
    db = session_factory()
    llm_calls = []

    class NewsLLM:
        async def analyze(self, user_message, system_prompt, context):
            llm_calls.append(
                {
                    "user_message": user_message,
                    "system_prompt": system_prompt,
                    "context": context,
                }
            )
            return "Headline-only assessment with cited sources."

    try:
        apple = seed_portfolio(db)
        db.add_all(
            [
                CompanyNews(
                    symbol=apple.id,
                    headline="Apple earnings beat estimates on strong iPhone demand",
                    description="The publisher says quarterly revenue and demand increased.",
                    url="https://example.test/aapl-results",
                    source="Example Finance",
                    published_date=datetime(2026, 11, 4),
                ),
                CompanyNews(
                    symbol=apple.id,
                    headline="Rockets Keep Rolling With 109-93 Win Over Celtics",
                    url="https://example.test/sports",
                    source="Sports Desk",
                    published_date=datetime(2026, 11, 4),
                ),
                CompanyNews(
                    symbol=apple.id,
                    headline="finport-datapipeline added to PyPI",
                    url="https://example.test/pypi",
                    source="PyPI",
                    published_date=datetime(2026, 11, 4),
                ),
            ]
        )
        db.commit()

        output = await MarketResearchAgent().execute(
            AgentContext(
                user_message="Analyze my portfolio",
                metadata={"db": db, "llm_client": NewsLLM()},
            )
        )

        assert output.success
        assert output.data["stored_article_count"] == 3
        assert output.data["article_count"] == 1
        assert output.data["excluded_article_count"] == 2
        article = output.data["articles"][0]
        assert article["headline"].startswith("Apple earnings")
        assert "quarterly revenue" in article["description"]
        assert article["topics"] == ["earnings_and_results", "products_and_demand"]
        assert article["tone"] == "positive_wording"
        assert article["evidence_level"] == "headline_and_publisher_snippet"
        assert "article text was not fetched" in output.data["findings_by_symbol"][
            "AAPL"
        ]["summary"].lower()
        assert "headline" in output.data["limitations"][0].lower()
        question_headline = MarketResearchAgent._analyze_headline(
            "MSFT",
            "Does Microsoft's Prudent Approach to the AI Infrastructure Buildout Make the Stock a Buy?",
        )
        assert question_headline["tone"] == "not_clear_from_headline"
        assert output.data["llm_analysis_status"] == "available"
        assert output.data["llm_analysis"] == "Headline-only assessment with cited sources."
        assert "full article bodies have not been fetched" in llm_calls[0][
            "system_prompt"
        ].lower()
        assert len(
            llm_calls[0]["context"]["stored_portfolio_news"]["AAPL"]["articles"]
        ) == 1
        assert "publisher says" in llm_calls[0]["context"]["stored_portfolio_news"][
            "AAPL"
        ]["articles"][0]["description"]
        assert output.data["assessment"]["confidence"].startswith("Low")
    finally:
        db.close()
        engine.dispose()


def test_virtual_broker_prices_are_valued_by_risk_agent():
    engine, session_factory = make_session_factory()
    db = session_factory()
    try:
        asyncio.run(sync_virtual_broker(db))
        risk = asyncio.run(
            RiskManagerAgent().execute(
                AgentContext(user_message="Analyze risk.", metadata={"db": db})
            )
        )

        assert risk.success
        assert risk.data["status"] == "available"
        assert risk.data["unpriced_symbols"] == []
        assert Decimal(risk.data["total_valued_usd"]) == Decimal("6306.25")
        assert {
            position["price_source"]
            for position in risk.data["largest_positions"]
        } == {"virtual_broker"}
        assert any(
            "sample data" in item.lower()
            for item in risk.data["assessment"]["missing"]
        )
        assert {
            position["symbol"]: Decimal(position["weight_percent"])
            for position in risk.data["largest_positions"]
        } == {
            "AAPL": Decimal("1755") / Decimal("6306.25") * Decimal("100"),
            "MSFT": Decimal("1751.25") / Decimal("6306.25") * Decimal("100"),
            "NVDA": Decimal("2800") / Decimal("6306.25") * Decimal("100"),
        }
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_synthesis_agent_sends_specialist_results_to_llm():
    provider = StubProvider(
        route_response=(
            '["portfolio", "market_research", "macro", "risk", "valuation"]'
        )
    )
    client = LLMClient(provider)
    output = await SynthesisAgent().execute(
        AgentContext(
            user_message="Analyze my portfolio.",
            metadata={
                "llm_client": client,
                "agent_outputs": {
                    "portfolio": {"holdings_count": 1},
                    "_errors": ["market_research: unavailable"],
                },
            },
        )
    )

    assert output.success
    assert output.data["response"] == "Combined assessment."
    assert output.data["specialists_considered"] == ["portfolio"]
    assert provider.calls[0]["context"]["portfolio"]["holdings_count"] == 1
    assert "untrusted evidence" in provider.calls[0]["system_prompt"]
    assert "under 100 words" in provider.calls[0]["system_prompt"]
    assert "at most three short bullets" in provider.calls[0]["system_prompt"]
    assert "Combine overlapping specialist findings" in provider.calls[0]["system_prompt"]
    assert "one compact Markdown table" in provider.calls[0]["system_prompt"]
    assert "do not repeat table figures" in provider.calls[0]["system_prompt"]
    assert "Distinguish available historical growth from missing forward estimates" in (
        provider.calls[0]["system_prompt"]
    )


@pytest.mark.asyncio
async def test_synthesis_preserves_complete_detailed_company_report():
    provider = StubProvider()
    detailed_report = (
        "1. Executive summary\nD-Wave report.\n"
        "8. Key risks, evidence gaps, and sources\nSources listed."
    )
    output = await SynthesisAgent().execute(
        AgentContext(
            user_message="Prepare a detailed company profile for D-Wave Quantum.",
            metadata={
                "llm_client": LLMClient(provider),
                "agent_outputs": {
                    "market_research": {
                        "on_demand_analysis": detailed_report,
                    },
                    "valuation": {"findings": [{"claim": "Unrelated holding"}]},
                },
            },
        )
    )

    assert output.success
    assert output.data["response"] == detailed_report
    assert output.data["specialists_considered"] == ["market_research", "valuation"]
    assert provider.calls == []


class SessionCheckingAgent(BaseAgent):
    def __init__(self):
        super().__init__("session-check")
        self.session_ids = []

    async def execute(self, context):
        session = context.metadata["db"]
        self.session_ids.append(id(session))
        await asyncio.sleep(0)
        return self._create_output(True, {"session_id": id(session)})


def test_parallel_agents_receive_dedicated_database_sessions():
    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    sessions = []

    def session_factory():
        session = FakeSession()
        sessions.append(session)
        return session

    first = SessionCheckingAgent()
    second = SessionCheckingAgent()
    outputs = asyncio.run(
        execute_agents_parallel(
            [first, second],
            AgentContext(
                user_message="Question",
                metadata={"db_factory": session_factory},
            ),
        )
    )

    assert all(output.success for output in outputs)
    assert first.session_ids[0] != second.session_ids[0]
    assert len(sessions) == 2
    assert all(session.closed for session in sessions)


def test_chat_endpoint_runs_specialists_then_synthesis(monkeypatch):
    from app import routes

    engine, session_factory = make_session_factory()
    db = session_factory()
    try:
        seed_portfolio(db)
        provider = StubProvider(
            route_response=(
                '["portfolio", "market_research", "macro", "risk", "valuation"]'
            )
        )
        monkeypatch.setattr(routes, "llm_client", LLMClient(provider))
        monkeypatch.setattr(routes, "get_session_factory", lambda: session_factory)

        response = asyncio.run(
            chat_message(
                ChatMessage(message="Should I buy more Apple?"),
            )
        )

        assert response.response == "Combined assessment."
        assert response.agents_used == [
            "portfolio",
            "market_research",
            "macro",
            "risk",
            "valuation",
            "synthesis",
        ]
        assert response.analysis["synthesis"]["response"] == "Combined assessment."
        for name in (
            "portfolio",
            "market_research",
            "macro",
            "risk",
            "valuation",
        ):
            assert set(response.analysis[name]["assessment"]) == {
                "finding",
                "evidence",
                "meaning",
                "counterpoint",
                "confidence",
                "missing",
            }
        assert response.analysis["macro"]["status"] == "no_data"
        assert response.analysis["portfolio"]["holdings"][0]["price_source"] == "etoro"
        assert len(provider.calls) == 2
        assert "Select only the specialists needed" in provider.calls[0]["system_prompt"]
        synthesis_call = provider.calls[1]
        assert set(synthesis_call["context"]) >= {
            "portfolio",
            "market_research",
            "macro",
            "risk",
            "valuation",
        }
        assert "price_source" in synthesis_call["context"]["portfolio"]["holdings"][0]
        assert synthesis_call["context"]["macro"]["status"] == "no_data"
    finally:
        db.close()
        engine.dispose()


def test_news_service_persists_publisher_description_snippets():
    engine, session_factory = make_session_factory()
    db = session_factory()
    try:
        asset = seed_portfolio(db)
        article = NewsArticle(
            symbol="AAPL",
            headline="Apple reports results",
            url="https://example.test/results",
            source="Example News",
            published_date=datetime(2026, 11, 4),
            description="Publisher-provided summary snippet.",
        )

        assert NewsService._store_articles(db, asset.id, [article]) == 1
        stored = db.query(CompanyNews).filter_by(url=article.url).one()
        assert stored.description == "Publisher-provided summary snippet."
        assert NewsService.get_latest_news(db, "AAPL")[0]["description"] == (
            "Publisher-provided summary snippet."
        )
    finally:
        db.close()
        engine.dispose()


def test_chat_endpoint_rejects_unknown_agent_names(monkeypatch):
    from fastapi import HTTPException
    from app import routes

    engine, session_factory = make_session_factory()
    db = session_factory()
    monkeypatch.setattr(routes, "llm_client", LLMClient(StubProvider()))
    try:
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                chat_message(
                    ChatMessage(message="Analyze Apple.", include_agents=["missing"]),
                )
            )
        assert exc_info.value.status_code == 400
        assert "missing" in exc_info.value.detail
    finally:
        db.close()
        engine.dispose()
