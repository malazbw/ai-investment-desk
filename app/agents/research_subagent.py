"""
Research Subagent following LangChain subagents pattern.
https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

A subagent that handles research queries for stocks/companies.
Tier 1 (current): Valuation metrics (P/E, EPS, dividend, market cap, 52-week high/low)
Future Tier 2: News & events integration
Future Tier 3: SEC filing RAG search, earnings transcript analysis

It has its own tools and agent executor, runs independently.
Can be called by Main Agent as a tool.
"""
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ============================================================================
# RESEARCH TOOLS - TIER 1 (VALUATION METRICS)
# ============================================================================

@tool
def get_pe_ratio(ticker: str) -> str:
    """
    Get P/E (Price-to-Earnings) ratio for a stock.

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL)

    Returns:
        P/E ratio and valuation context
    """
    logger.info(f"[RESEARCH_TOOL] ✓ get_pe_ratio({ticker}) CALLED")

    valuation_data = {
        "MSFT": {"pe_ratio": 28.5, "status": "moderate", "industry_avg": 25.0},
        "AAPL": {"pe_ratio": 31.2, "status": "elevated", "industry_avg": 25.0},
        "NVDA": {"pe_ratio": 52.1, "status": "high", "industry_avg": 25.0},
        "TSLA": {"pe_ratio": 45.3, "status": "high", "industry_avg": 15.0},
    }

    data = valuation_data.get(ticker, {"pe_ratio": None, "status": "unknown"})

    if data["pe_ratio"]:
        result = f"""
P/E Ratio for {ticker}:
- P/E Ratio: {data['pe_ratio']}
- Status: {data['status'].capitalize()} vs industry
- Industry Average: {data.get('industry_avg', 'N/A')}
"""
    else:
        result = f"P/E ratio data not available for {ticker}"

    return result


@tool
def get_eps(ticker: str) -> str:
    """
    Get EPS (Earnings Per Share) for a stock.

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL)

    Returns:
        Current and trailing EPS
    """
    logger.info(f"[RESEARCH_TOOL] ✓ get_eps({ticker}) CALLED")

    eps_data = {
        "MSFT": {"trailing_eps": 9.89, "forward_eps": 10.50, "growth": "6.2%"},
        "AAPL": {"trailing_eps": 5.95, "forward_eps": 6.50, "growth": "9.2%"},
        "NVDA": {"trailing_eps": 3.45, "forward_eps": 5.20, "growth": "50.7%"},
        "TSLA": {"trailing_eps": 2.81, "forward_eps": 3.50, "growth": "24.6%"},
    }

    data = eps_data.get(ticker)

    if data:
        result = f"""
EPS (Earnings Per Share) for {ticker}:
- Trailing EPS: ${data['trailing_eps']}
- Forward EPS: ${data['forward_eps']}
- Growth Rate: {data['growth']}
"""
    else:
        result = f"EPS data not available for {ticker}"

    return result


@tool
def get_dividend_yield(ticker: str) -> str:
    """
    Get dividend yield for a stock.

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL)

    Returns:
        Dividend yield and payment info
    """
    logger.info(f"[RESEARCH_TOOL] ✓ get_dividend_yield({ticker}) CALLED")

    dividend_data = {
        "MSFT": {"yield": 0.72, "annual_dividend": 3.00, "payout_ratio": 25},
        "AAPL": {"yield": 0.43, "annual_dividend": 2.52, "payout_ratio": 15},
        "NVDA": {"yield": 0.03, "annual_dividend": 0.04, "payout_ratio": 1},
        "TSLA": {"yield": 0.0, "annual_dividend": 0.0, "payout_ratio": 0},
    }

    data = dividend_data.get(ticker)

    if data:
        yield_info = f"Dividend Yield: {data['yield']}%" if data['yield'] > 0 else "No dividend"
        result = f"""
Dividend Information for {ticker}:
- {yield_info}
- Annual Dividend: ${data['annual_dividend']}
- Payout Ratio: {data['payout_ratio']}%
"""
    else:
        result = f"Dividend data not available for {ticker}"

    return result


@tool
def get_market_cap(ticker: str) -> str:
    """
    Get market capitalization and size classification for a stock.

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL)

    Returns:
        Market cap and company size
    """
    logger.info(f"[RESEARCH_TOOL] ✓ get_market_cap({ticker}) CALLED")

    market_cap_data = {
        "MSFT": {"market_cap": 3200, "classification": "mega-cap", "currency": "USD (Billions)"},
        "AAPL": {"market_cap": 3150, "classification": "mega-cap", "currency": "USD (Billions)"},
        "NVDA": {"market_cap": 1850, "classification": "mega-cap", "currency": "USD (Billions)"},
        "TSLA": {"market_cap": 950, "classification": "large-cap", "currency": "USD (Billions)"},
    }

    data = market_cap_data.get(ticker)

    if data:
        result = f"""
Market Capitalization for {ticker}:
- Market Cap: ${data['market_cap']} {data['currency']}
- Classification: {data['classification'].capitalize()}
"""
    else:
        result = f"Market cap data not available for {ticker}"

    return result


@tool
def get_52_week_range(ticker: str) -> str:
    """
    Get 52-week high and low for a stock.

    Args:
        ticker: Stock symbol (e.g., MSFT, AAPL)

    Returns:
        52-week price range and proximity to highs/lows
    """
    logger.info(f"[RESEARCH_TOOL] ✓ get_52_week_range({ticker}) CALLED")

    range_data = {
        "MSFT": {"high": 425, "low": 295, "current": 420, "low_proximity": "92% from low"},
        "AAPL": {"high": 245, "low": 170, "current": 235, "low_proximity": "88% from low"},
        "NVDA": {"high": 1050, "low": 650, "current": 920, "low_proximity": "77% from low"},
        "TSLA": {"high": 350, "low": 155, "current": 285, "low_proximity": "84% from low"},
    }

    data = range_data.get(ticker)

    if data:
        result = f"""
52-Week Range for {ticker}:
- 52-Week High: ${data['high']}
- 52-Week Low: ${data['low']}
- Current Price: ${data['current']}
- Position: {data['low_proximity']}
"""
    else:
        result = f"52-week range data not available for {ticker}"

    return result


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
        get_pe_ratio,
        get_eps,
        get_dividend_yield,
        get_market_cap,
        get_52_week_range,
    ]

    # Define system prompt for this subagent
    system_prompt = """You are a financial research specialist focusing on company valuation.

You have access to Tier 1 valuation tools:
- get_pe_ratio: P/E ratio and valuation status
- get_eps: Earnings per share data
- get_dividend_yield: Dividend information
- get_market_cap: Market capitalization and size classification
- get_52_week_range: 52-week high/low price range

When asked about a company's valuation metrics, use the appropriate tools to gather data.
Provide clear analysis of valuation metrics, comparing to industry averages and identifying if the stock is cheap, fair, or expensive."""

    # Create agent using LangChain
    agent = create_agent(
        model=llm_model,
        tools=tools,
        system_prompt=system_prompt,
    )

    return agent


# ============================================================================
# WRAPPER TOOL FOR MAIN AGENT
# ============================================================================

def create_research_subagent_tool(llm_model: Any):
    """
    Create a tool that wraps the Research Subagent.
    This tool will be available to the Main Agent.

    Args:
        llm_model: LangChain chat model

    Returns:
        Tool that calls research subagent
    """

    # Create the research subagent
    logger.info("[RESEARCH_TOOL] Creating research agent...")
    research_agent = create_research_subagent(llm_model)
    logger.info("[RESEARCH_TOOL] ✓ Research agent created")

    @tool
    async def research_subagent(query: str) -> str:
        """
        Research Subagent - Handles questions about company valuation and fundamentals (Tier 1).

        Can answer questions about:
        - P/E ratio and valuation status
        - Earnings per share (EPS)
        - Dividend yield and payout info
        - Market cap and company size
        - 52-week price range and trends

        Args:
            query: Question about company valuation/research (e.g., "What's the P/E ratio for Microsoft?")

        Returns:
            Research analysis with metrics
        """
        logger.info("\n" + "-"*80)
        logger.info("[RESEARCH_AGENT] ✓ CALLED BY MAIN AGENT")
        logger.info(f"[RESEARCH_AGENT] Query: {query}")
        logger.info("-"*80)

        try:
            logger.info("[RESEARCH_AGENT] Invoking research agent...")
            result = await research_agent.ainvoke({
                "messages": [HumanMessage(content=query)]
            })
            logger.info("[RESEARCH_AGENT] ✓ Research agent completed")
            messages = result.get("messages", [])
            if not messages:
                return "The research agent returned no response."

            content = messages[-1].content
            if isinstance(content, str):
                output = content
            elif isinstance(content, list):
                output = "".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                output = str(content)
            logger.info(f"[RESEARCH_AGENT] Output: {output[:100]}...")
            logger.info("-"*80)
            return output
        except Exception as e:
            logger.error(f"[RESEARCH_AGENT] ✗ ERROR (will return placeholder): {e}")
            logger.error("-"*80)
            # Return a passable result to avoid breaking the Main Agent flow
            return "Research data temporarily unavailable. Please try again."

    return research_subagent
