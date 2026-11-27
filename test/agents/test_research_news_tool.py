import asyncio
import json
from datetime import datetime, timezone

from app.agents import research_subagent
from app.data_sources.news_fetcher import NewsArticle


def test_get_company_news_returns_source_attributed_articles(monkeypatch):
    article = NewsArticle(
        symbol="MSFT",
        headline="Microsoft announces an update",
        url="https://example.com/news",
        source="Example News",
        published_date=datetime(2026, 11, 27, tzinfo=timezone.utc),
        description="A publisher-provided summary.",
    )
    calls = []

    async def search_newsapi(query, days):
        calls.append((query, days))
        return [article]

    monkeypatch.setattr(
        research_subagent.NewsSearcher, "search_newsapi", search_newsapi
    )

    result = json.loads(
        asyncio.run(
            research_subagent.get_company_news.ainvoke(
                {"ticker": "msft", "company_name": "Microsoft", "days": 3}
            )
        )
    )

    assert calls == [('"Microsoft" OR MSFT', 3)]
    assert result["status"] == "ok"
    assert result["ticker"] == "MSFT"
    assert result["source"] == "NewsAPI"
    assert result["evidence_level"] == "headline_and_publisher_snippet"
    assert result["articles"] == [
        {
            "headline": "Microsoft announces an update",
            "publisher": "Example News",
            "published_at": "2026-11-27T00:00:00+00:00",
            "url": "https://example.com/news",
            "snippet": "A publisher-provided summary.",
        }
    ]


def test_get_company_news_rejects_invalid_ticker_before_search(monkeypatch):
    async def search_newsapi(*args, **kwargs):
        raise AssertionError("Search should not run for an invalid ticker")

    monkeypatch.setattr(
        research_subagent.NewsSearcher, "search_newsapi", search_newsapi
    )

    result = json.loads(
        asyncio.run(
            research_subagent.get_company_news.ainvoke(
                {"ticker": "not a ticker"}
            )
        )
    )

    assert result["status"] == "error"
    assert result["error"] == "Invalid ticker symbol: not a ticker"


def test_get_company_news_returns_no_results_status(monkeypatch):
    async def search_newsapi(*args, **kwargs):
        return []

    monkeypatch.setattr(
        research_subagent.NewsSearcher, "search_newsapi", search_newsapi
    )

    result = json.loads(
        asyncio.run(
            research_subagent.get_company_news.ainvoke({"ticker": "MSFT"})
        )
    )

    assert result["status"] == "no_results"
    assert result["articles"] == []


def test_create_research_subagent_registers_news_tool_and_returns_agent(monkeypatch):
    expected_agent = object()
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return expected_agent

    monkeypatch.setattr(research_subagent, "create_agent", fake_create_agent)

    agent = research_subagent.create_research_subagent(object())

    assert agent is expected_agent
    assert captured["tools"] == [
        research_subagent.get_valuation_metrics,
        research_subagent.get_company_news,
    ]
