"""Tier 1 company research agent backed by Yahoo Finance fundamentals."""
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

from app.services.yahoo_finance import YahooFinanceService

logger = logging.getLogger(__name__)


@tool(
    "get_tier1_fundamentals",
    description=(
        "Fetch current company fundamentals for a public stock ticker, including "
        "valuation ratios, EPS, market capitalization, dividend data, and 52-week "
        "price range. Returns the source service's available fields and fetch time."
    ),
)
async def get_tier1_fundamentals(ticker: str) -> dict[str, Any]:
    """Fetch Tier 1 fundamentals for a ticker through the existing Yahoo Finance service."""
    normalized_ticker = ticker.strip().upper()
    logger.info("[RESEARCH_TOOL] Fetching Tier 1 fundamentals for %s", normalized_ticker)
    raw_data = await YahooFinanceService().get_fundamentals(normalized_ticker)
    if raw_data.get("error"):
        return {
            "symbol": normalized_ticker,
            "status": "unavailable",
            "reason": raw_data["error"],
        }

    valuation = raw_data.get("valuation", {})
    earnings = raw_data.get("earnings", {})
    price_action = raw_data.get("price_action", {})
    income = raw_data.get("income", {})
    return {
        "symbol": normalized_ticker,
        "status": "available",
        "source": "Yahoo Finance",
        "fetched_at": raw_data.get("fetched_at"),
        "valuation": {
            "pe_trailing": valuation.get("pe_trailing"),
            "pe_forward": valuation.get("pe_forward"),
            "market_cap": valuation.get("market_cap"),
        },
        "earnings": {
            "eps_trailing": earnings.get("eps_trailing"),
            "eps_current_year": earnings.get("eps_current_year"),
            "eps_forward": earnings.get("eps_forward"),
        },
        "dividends": {
            "yield": income.get("dividend_yield"),
            "trailing_annual_dividend": income.get("trailing_annual_dividend"),
            "five_year_average_yield": income.get("five_year_avg_dividend_yield"),
        },
        "price_range": {
            "current_price": price_action.get("current_price"),
            "fifty_two_week_high": price_action.get("fifty_two_week_high"),
            "fifty_two_week_low": price_action.get("fifty_two_week_low"),
        },
    }


def create_research_subagent(llm_model: Any):
    """Create the Tier 1 research agent with a live fundamentals tool."""
    return create_agent(
        model=llm_model,
        tools=[get_tier1_fundamentals],
        system_prompt=(
            "You are a company research assistant focused on Tier 1 fundamentals. "
            "Ground factual claims in the data returned by your tool. State clearly "
            "when a metric is missing or unavailable, and do not invent values. "
            "Do not provide news or event research, SEC filing search, transcript "
            "analysis, or unsupported valuation conclusions."
        ),
        name="Tier 1 Research Agent",
    )


def create_research_subagent_tool(llm_model: Any):
    """Wrap the research agent as a tool that can be called by the main agent."""
    research_agent = create_research_subagent(llm_model)

    @tool(
        "research_subagent",
        description=(
            "Answer questions about a public company's Tier 1 fundamentals, such as "
            "P/E, EPS, market capitalization, dividends, and 52-week price range."
        ),
    )
    async def call_research_subagent(query: str) -> str:
        result = await research_agent.ainvoke(
            {"messages": [{"role": "user", "content": query}]}
        )
        messages = result.get("messages", [])
        if not messages:
            return "The research agent returned no response."

        content = messages[-1].content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return str(content)

    return call_research_subagent
