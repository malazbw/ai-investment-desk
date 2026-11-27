"""Tier 1 company research agent backed by Yahoo Finance fundamentals."""
import logging
from typing import Any

import yfinance as yf
from langchain.agents import create_agent
from langchain_core.tools import tool

from app.services.yahoo_finance import YahooFinanceService

logger = logging.getLogger(__name__)


# ============================================================================
# RESEARCH TOOLS - TIER 1 (VALUATION METRICS)
# ============================================================================

def _classify_market_cap(cap: float) -> str:
    if cap >= 200_000_000_000:
        return "mega-cap"
    elif cap >= 10_000_000_000:
        return "large-cap"
    elif cap >= 2_000_000_000:
        return "mid-cap"
    elif cap >= 300_000_000:
        return "small-cap"
    else:
        return "micro-cap"


@tool
def get_valuation_metrics(ticker: str) -> str:
    """
    Get comprehensive valuation metrics for a stock (Tier 1 fundamental analysis).

    Returns all key valuation metrics in one call:
    - P/E ratios (trailing and forward)
    - EPS (earnings per share)
    - Dividend yield and payout info
    - Market capitalization and classification
    - 52-week price range

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL, NVDA)

    Returns:
        Comprehensive valuation analysis
    """
    logger.info(f"[RESEARCH_TOOL] ✓ get_valuation_metrics({ticker}) CALLED")

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        company_name = info.get("longName", ticker)
        result = f"\n📊 Valuation Metrics for {company_name} ({ticker})\n"
        result += "=" * 60 + "\n"

        # P/E Ratios
        trailing_pe = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        if trailing_pe or forward_pe:
            result += "\n🔢 Valuation Ratios:\n"
            result += f"  - Trailing P/E: {trailing_pe if trailing_pe else 'N/A'}\n"
            result += f"  - Forward P/E: {forward_pe if forward_pe else 'N/A'}\n"

        # EPS
        trailing_eps = info.get("trailingEps")
        forward_eps = info.get("forwardEps")
        if trailing_eps or forward_eps:
            result += "\n💰 Earnings Per Share:\n"
            result += f"  - Trailing EPS: ${trailing_eps if trailing_eps else 'N/A'}\n"
            result += f"  - Forward EPS: ${forward_eps if forward_eps else 'N/A'}\n"

        # Dividend
        dividend_yield = info.get("dividendYield")
        trailing_annual_dividend = info.get("trailingAnnualDividendRate")
        payout_ratio = info.get("payoutRatio")
        if dividend_yield is not None or trailing_annual_dividend:
            result += "\n🎁 Dividend Information:\n"
            yield_pct = (dividend_yield * 100) if dividend_yield else 0
            result += f"  - Dividend Yield: {yield_pct:.2f}%\n"
            result += f"  - Annual Dividend: ${trailing_annual_dividend if trailing_annual_dividend else 'N/A'}\n"
            result += f"  - Payout Ratio: {(payout_ratio * 100) if payout_ratio else 'N/A'}%\n"

        # Market Cap
        market_cap = info.get("marketCap")
        if market_cap:
            market_cap_billions = market_cap / 1_000_000_000
            classification = _classify_market_cap(market_cap)
            result += "\n🏢 Market Capitalization:\n"
            result += f"  - Market Cap: ${market_cap_billions:.2f}B USD\n"
            result += f"  - Classification: {classification.capitalize()}\n"

        # 52-Week Range
        week_52_high = info.get("fiftyTwoWeekHigh")
        week_52_low = info.get("fiftyTwoWeekLow")
        current_price = info.get("currentPrice")
        if week_52_high and week_52_low and current_price:
            range_pct = ((current_price - week_52_low) / (week_52_high - week_52_low)) * 100 if (week_52_high - week_52_low) > 0 else 0
            result += "\n📈 52-Week Price Range:\n"
            result += f"  - Current Price: ${current_price:.2f}\n"
            result += f"  - 52-Week High: ${week_52_high:.2f}\n"
            result += f"  - 52-Week Low: ${week_52_low:.2f}\n"
            result += f"  - Position: {range_pct:.1f}% from low\n"

        if result.count("\n") <= 2:
            return f"Valuation data not available for {ticker}"

        return result
    except Exception as e:
        logger.error(f"Error fetching valuation metrics for {ticker}: {e}")
        return f"Valuation data not available for {ticker}"


# ============================================================================
# RESEARCH SUBAGENT
# ============================================================================

def create_research_subagent(llm_model: Any):
    """
    Create Research Subagent with Tier 1 valuation tools.

    This subagent:
    - Has access to valuation metric tools
    - Runs independently
    - Can be called by Main Agent as a tool

    Args:
        llm_model: LangChain chat model (Gemini)

    Returns:
        Agent (CompiledStateGraph)
    """
    logger.info("[research_subagent] Creating Research Subagent")

    # Define Tier 1 tools (valuation metrics)
    tools = [
        get_valuation_metrics,
    ]

    # Define system prompt for this subagent
    system_prompt = """You are a financial research specialist focusing on company valuation.

You have access to the get_valuation_metrics tool which provides:
- P/E ratios (trailing and forward)
- Earnings per share (EPS)
- Dividend yield and payout information
- Market capitalization and company size classification
- 52-week price range and current position

When asked about a company's valuation metrics, use the get_valuation_metrics tool to gather comprehensive data.
Provide clear analysis of valuation metrics and identify if the stock appears cheap, fair, or expensive."""

    # Create agent using LangChain
    agent = create_agent(
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
