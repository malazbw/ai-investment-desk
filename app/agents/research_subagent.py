"""Company research agent backed by Yahoo Finance fundamentals and NewsAPI."""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import yfinance as yf
from langchain.agents import create_agent
from langchain_core.tools import tool

from app.data_sources.news_fetcher import NewsSearcher

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


@tool
async def get_company_news(
    ticker: str, company_name: str = "", days: int = 7
) -> str:
    """Fetch recent company headlines and publisher snippets from NewsAPI.

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL, NVDA).
        company_name: Company name to improve matching (e.g., Microsoft).
        days: Number of days to search, from 1 to 30.
    """
    normalized_ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", normalized_ticker):
        return json.dumps(
            {
                "status": "error",
                "ticker": normalized_ticker,
                "error": f"Invalid ticker symbol: {ticker}",
            }
        )
    if not 1 <= days <= 30:
        return json.dumps(
            {
                "status": "error",
                "ticker": normalized_ticker,
                "error": "The news search period must be between 1 and 30 days.",
            }
        )

    normalized_name = company_name.strip()
    query = (
        f'"{normalized_name}" OR {normalized_ticker}'
        if normalized_name
        else normalized_ticker
    )
    try:
        articles = await NewsSearcher.search_newsapi(query, days=days)
    except RuntimeError as exc:
        logger.warning("NewsAPI research failed for %s: %s", normalized_ticker, exc)
        return json.dumps(
            {
                "status": "error",
                "ticker": normalized_ticker,
                "source": "NewsAPI",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "status": "ok" if articles else "no_results",
            "ticker": normalized_ticker,
            "company_name": normalized_name or None,
            "source": "NewsAPI",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "search_window_days": days,
            "evidence_level": "headline_and_publisher_snippet",
            "articles": [
                {
                    "headline": article.headline,
                    "publisher": article.source,
                    "published_at": article.published_date.isoformat(),
                    "url": article.url,
                    "snippet": article.description,
                }
                for article in articles
            ],
        },
        ensure_ascii=False,
    )


# ============================================================================
# RESEARCH SUBAGENT
# ============================================================================

def create_research_subagent(llm_model: Any):
    """
    Create Research Subagent with valuation and company-news tools.

    This subagent:
    - Has access to valuation metrics and recent company news
    - Runs independently
    - Can be called by Main Agent as a tool

    Args:
        llm_model: LangChain chat model (Gemini)

    Returns:
        Agent (CompiledStateGraph)
    """
    logger.info("[research_subagent] Creating Research Subagent")

    return create_agent(
        model=llm_model,
        tools=[get_valuation_metrics, get_company_news],
        system_prompt=(
            "You are an objective financial and company research assistant. Your goal is to provide accurate, "
            "well-structured company profiles and market updates grounded strictly in retrieved data.\n\n"

            "### Tool Usage & Routing\n"
            "1. **Fundamental & Financial Data:** Call `get_valuation_metrics` ONLY when explicitly asked about "
            "valuation ratios (P/E, EV/EBITDA, P/S), market cap, revenue, profitability, or balance sheet health.\n"
            "2. **Qualitative & Recent Events:** Call `get_company_news` when asked about recent developments, "
            "earnings announcements, leadership changes, M&A, or market sentiment.\n"
            "3. **Comprehensive Queries:** If a user explicitly asks for 'full analysis', 'investment thesis', "
            "or 'complete profile', call BOTH tools in parallel. Otherwise, infer nothing - only call tools the user mentions.\n"
            "4. **Disambiguation:** If a company name is ambiguous, resolve or clarify the exact ticker before running tools.\n\n"

            "### Data Integrity & Grounding Rules\n"
            "- **Strict Grounding:** Every numerical figure, date, and factual claim must come directly from tool outputs. "
            "Never rely on pre-trained memory for stock prices, valuation multiples, or recent news.\n"
            "- **Temporal Anchoring:** Explicitly state the reporting period or date for all metrics (e.g., 'TTM as of Q3 2026') "
            "and publication dates for news headlines.\n"
            "- **Missing Data & Tool Errors:** If a metric is null, missing, or a tool returns an error, explicitly state: "
            "'Data for [metric/topic] is currently unavailable.' Do not estimate, interpolate, or extrapolate.\n"
            "- **Conflict Resolution:** If news conflicts with metrics, present both with their respective timestamps.\n\n"

            "### Response Formatting\n"
            "- Lead with a 2-sentence executive summary answering the user's core question.\n"
            "- Present metrics in a clean Markdown table (Metric | Value | Period/Notes).\n"
            "- Present news as a chronological bulleted list with dates and source attribution.\n"
            "- Maintain a neutral, analytical tone. Never offer personalized financial advice."
        ),
        name="Company Research Agent",
    )


def create_research_subagent_tool(llm_model: Any):
    """Wrap the research agent as a tool that can be called by the main agent."""
    research_agent = create_research_subagent(llm_model)

    @tool(
        "research_subagent",
        description=(
            "Research a public company's fundamentals or recent news. Covers P/E, EPS, "
            "market capitalization, dividends, 52-week range, and NewsAPI headlines."
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
