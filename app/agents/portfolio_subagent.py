"""Read-only portfolio data tools backed by the application database."""
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

from app.database import get_session_factory
from app.models import Holding

logger = logging.getLogger(__name__)


@tool
def get_holdings() -> list[dict[str, str | None]]:
    """Return the user's stored holdings without broker details."""
    logger.info("[PORTFOLIO_TOOL] get_holdings() called")
    session = get_session_factory()()
    try:
        holdings = session.query(Holding).all()
        return [
            {
                "symbol": holding.asset.symbol,
                "quantity": str(holding.quantity),
                "current_value": (
                    str(holding.current_value)
                    if holding.current_value is not None
                    else None
                ),
                "currency": holding.asset.currency,
            }
            for holding in holdings
        ]
    finally:
        session.close()


def create_portfolio_subagent(llm_model: Any):
    """Create a portfolio agent with the database-backed holdings tool."""
    return create_agent(
        model=llm_model,
        tools=[get_holdings],
        system_prompt="You are a portfolio assistant. Base answers on information returned by your tools.",
    )
