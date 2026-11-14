"""
Portfolio Subagent following LangChain subagents pattern.
A subagent that handles all portfolio-related queries.
It has its own tools and agent executor, runs independently.
Can be called by Main Agent as a tool.
"""
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ============================================================================
# PORTFOLIO SUBAGENT TOOLS
# ============================================================================

@tool
def get_portfolio_summary() -> str:
    """
    Get complete portfolio summary including total value, gain/loss, and composition.

    Returns:
        Portfolio overview as a formatted string
    """
    logger.info("[portfolio_subagent] Getting portfolio summary")

    # Mock data for now - would query database in real implementation
    portfolio_data = {
        "total_value": 150000,
        "total_gain_loss": 22500,
        "gain_loss_percent": 15.0,
        "number_of_positions": 8,
        "number_of_brokers": 2,
    }

    return f"""
Portfolio Summary:
- Total Value: ${portfolio_data['total_value']:,.0f}
- Total Gain/Loss: ${portfolio_data['total_gain_loss']:,.0f} ({portfolio_data['gain_loss_percent']:.1f}%)
- Number of Positions: {portfolio_data['number_of_positions']}
- Number of Brokers: {portfolio_data['number_of_brokers']}
"""


@tool
def get_holdings_by_broker() -> str:
    """
    Get holdings grouped by broker.

    Returns:
        Holdings breakdown by broker
    """
    logger.info("[portfolio_subagent] Getting holdings by broker")

    holdings_data = {
        "etoro": [
            {"ticker": "MSFT", "quantity": 10, "price": 350, "value": 3500},
            {"ticker": "AAPL", "quantity": 15, "price": 175, "value": 2625},
        ],
        "virtual_broker": [
            {"ticker": "NVDA", "quantity": 5, "price": 900, "value": 4500},
            {"ticker": "TSLA", "quantity": 8, "price": 250, "value": 2000},
        ]
    }

    result = "\nHoldings by Broker:\n"
    total_value = 0

    for broker, holdings in holdings_data.items():
        broker_value = sum(h["value"] for h in holdings)
        total_value += broker_value
        result += f"\n{broker.upper()}:\n"
        result += f"  Total Value: ${broker_value:,.0f}\n"
        result += f"  Positions: {len(holdings)}\n"
        for h in holdings:
            result += f"    - {h['ticker']}: {h['quantity']} @ ${h['price']} = ${h['value']:,.0f}\n"

    result += f"\nTotal across all brokers: ${total_value:,.0f}\n"
    return result


@tool
def get_sector_allocation() -> str:
    """
    Get portfolio allocation by sector.

    Returns:
        Sector breakdown
    """
    logger.info("[portfolio_subagent] Getting sector allocation")

    sector_allocation = {
        "Technology": {"value": 12500, "percent": 50},
        "Financials": {"value": 5000, "percent": 20},
        "Healthcare": {"value": 5000, "percent": 20},
        "Consumer": {"value": 2500, "percent": 10},
    }

    result = "\nSector Allocation:\n"
    for sector, data in sector_allocation.items():
        result += f"  {sector}: ${data['value']:,.0f} ({data['percent']:.0f}%)\n"

    return result


@tool
def get_concentration_analysis() -> str:
    """
    Analyze portfolio concentration risks.

    Returns:
        Concentration metrics and risk assessment
    """
    logger.info("[portfolio_subagent] Analyzing concentration")

    concentration_data = {
        "largest_position": {"ticker": "MSFT", "value": 3500, "percent": 14},
        "top_3_positions": 45,
        "top_5_positions": 65,
        "tech_sector_percent": 50,
        "single_broker_percent": 60,
    }

    result = "\nConcentration Analysis:\n"
    result += f"  Largest Position: {concentration_data['largest_position']['ticker']} at {concentration_data['largest_position']['percent']}%\n"
    result += f"  Top 3 Positions: {concentration_data['top_3_positions']}% of portfolio\n"
    result += f"  Top 5 Positions: {concentration_data['top_5_positions']}% of portfolio\n"
    result += f"  Technology Sector: {concentration_data['tech_sector_percent']}% (HIGH concentration)\n"
    result += f"  Single Broker: {concentration_data['single_broker_percent']}% (HIGH concentration)\n"
    result += f"\n⚠️  Risk Level: HIGH - Concentrated in tech and single broker\n"

    return result


# ============================================================================
# PORTFOLIO SUBAGENT
# ============================================================================

def create_portfolio_subagent(llm_model: Any):
    """
    Create Portfolio Subagent with its own tools.

    This subagent:
    - Has access to portfolio-specific tools
    - Runs independently
    - Can be called by Main Agent as a tool

    Args:
        llm_model: LangChain chat model

    Returns:
        Agent for portfolio subagent
    """
    logger.info("[portfolio_subagent] Creating Portfolio Subagent")

    # Define tools available to this subagent
    tools = [
        get_portfolio_summary,
        get_holdings_by_broker,
        get_sector_allocation,
        get_concentration_analysis,
    ]

    # Define system prompt for this subagent
    system_prompt = """You are a portfolio analysis specialist.

You have access to tools that provide information about the user's portfolio:
- get_portfolio_summary: Overall portfolio metrics
- get_holdings_by_broker: Holdings grouped by broker
- get_sector_allocation: Portfolio allocation by sector
- get_concentration_analysis: Risk and concentration metrics

When asked about portfolio-related topics, use the appropriate tools to gather information and provide a clear, structured analysis.
Focus on providing insights about allocation, concentration, and risk."""

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

def create_portfolio_subagent_tool(llm_model: Any):
    """
    Create a tool that wraps the Portfolio Subagent.
    This tool will be available to the Main Agent.

    Args:
        llm_model: LangChain chat model

    Returns:
        Tool that calls portfolio subagent
    """

    # Create the portfolio subagent
    portfolio_agent = create_portfolio_subagent(llm_model)

    @tool
    async def portfolio_subagent(query: str) -> str:
        """
        Portfolio Subagent - Handles questions about user's portfolio.

        Can answer questions about:
        - Holdings and positions
        - Portfolio allocation by broker
        - Sector allocation
        - Concentration risks
        - Gains/losses

        Args:
            query: Question about the portfolio

        Returns:
            Portfolio analysis
        """
        logger.info(f"[portfolio_subagent] Processing query: {query}")

        try:
            result = await portfolio_agent.ainvoke({"input": query})
            return result.get("output", str(result))
        except Exception as e:
            logger.error(f"[portfolio_subagent] Error: {e}", exc_info=True)
            return f"Error processing portfolio query: {str(e)}"

    return portfolio_subagent
