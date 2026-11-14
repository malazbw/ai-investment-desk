"""
Tool definitions and executors for Research Agent.
Tools are presented to LLM for intelligent selection.
"""
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List

import yfinance as yf

logger = logging.getLogger(__name__)


# Tool definitions - presented to LLM for tool selection
RESEARCH_TOOLS = [
    {
        "name": "get_stock_valuation",
        "description": "Get valuation metrics for a stock including P/E ratio, EPS, dividend yield, market cap, and 52-week high/low",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., MSFT, AAPL, NVDA)"
                }
            },
            "required": ["ticker"]
        }
    }
    # TODO: Tier 2 tool
    # {
    #     "name": "get_news",
    #     "description": "Get recent news and sentiment analysis for a stock",
    #     "input_schema": {...}
    # },
    # TODO: Tier 3 tool
    # {
    #     "name": "search_sec_filings",
    #     "description": "Search SEC filings for specific information",
    #     "input_schema": {...}
    # }
]


async def get_stock_valuation(ticker: str) -> Dict[str, Any]:
    """
    Tier 1 tool: Fetch valuation metrics from yfinance.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with valuation data (pe_ratio, eps, dividend, market_cap, 52-week high/low, etc.)
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        data = {
            "ticker": ticker,
            "company_name": info.get("longName", ticker),
            "currency": info.get("currency", "USD"),
            "price": info.get("currentPrice"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "dividend_rate": info.get("dividendRate"),
            "dividend_yield": info.get("dividendYield"),
            "market_cap": info.get("marketCap"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "beta": info.get("beta"),
            "profit_margins": info.get("profitMargins"),
            "revenue": info.get("totalRevenue"),
            "gross_profit": info.get("grossProfits"),
            "cash": info.get("totalCash"),
            "debt": info.get("totalDebt"),
        }

        logger.info(f"Fetched valuation data for {ticker}")

        return {
            "tool": "get_stock_valuation",
            "success": True,
            "data": data,
            "fetched_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to fetch valuation data for {ticker}: {e}")
        return {
            "tool": "get_stock_valuation",
            "success": False,
            "error": str(e),
            "fetched_at": datetime.utcnow().isoformat()
        }


# TODO: Tier 2 tool
async def get_news(ticker: str, days: int = 7) -> Dict[str, Any]:
    """
    Tier 2 tool: Fetch news and sentiment analysis from NewsAPI.
    """
    return {
        "tool": "get_news",
        "status": "not_implemented",
        "message": "Tier 2 news tool coming soon"
    }


# TODO: Tier 3 tool
async def search_sec_filings(ticker: str, query: str, filing_type: str = None) -> Dict[str, Any]:
    """
    Tier 3 tool: Search SEC filings using RAG.
    """
    return {
        "tool": "search_sec_filings",
        "status": "not_implemented",
        "message": "Tier 3 SEC filing RAG tool coming soon"
    }


# Tool executor registry
TOOL_EXECUTORS: Dict[str, Callable] = {
    "get_stock_valuation": get_stock_valuation,
    "get_news": get_news,
    "search_sec_filings": search_sec_filings,
}


async def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool

    Returns:
        Tool result
    """
    if tool_name not in TOOL_EXECUTORS:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }

    executor = TOOL_EXECUTORS[tool_name]
    result = await executor(**tool_args)
    return result
