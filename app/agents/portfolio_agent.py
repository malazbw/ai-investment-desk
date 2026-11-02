"""
Portfolio Agent - analyzes user's holdings and portfolio
"""
import time
from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.services import PortfolioService
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PortfolioAgent(BaseAgent):
    """Agent that queries portfolio data from database"""

    def __init__(self):
        super().__init__(name="portfolio")

    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Get portfolio data for analysis.

        Args:
            context: Must contain 'db' in metadata

        Returns:
            AgentOutput with portfolio summary and holdings
        """
        start_time = time.time()

        try:
            db = context.metadata.get("db")
            if not db:
                raise ValueError("Database session not provided in context")

            # Get portfolio summary
            summary = PortfolioService.get_portfolio_summary(db)

            # Get all holdings
            holdings = PortfolioService.get_all_holdings(db)

            # Get recent transactions
            transactions = PortfolioService.get_recent_transactions(db, days=30)

            # Format data
            data = {
                "portfolio_summary": {
                    "total_value": float(summary.total_value) if summary.total_value else 0,
                    "total_cost": float(summary.total_cost) if summary.total_cost else 0,
                    "total_gain_loss": float(summary.total_gain_loss) if summary.total_gain_loss else 0,
                    "total_gain_loss_percent": float(summary.total_gain_loss_percent) if summary.total_gain_loss_percent else 0,
                    "cash_value": float(summary.cash_value) if summary.cash_value else 0,
                },
                "holdings": [
                    {
                        "symbol": h.asset.symbol if h.asset else "unknown",
                        "name": h.asset.name if h.asset else "unknown",
                        "quantity": float(h.quantity),
                        "average_cost": float(h.average_cost),
                        "total_cost": float(h.total_cost),
                        "current_price": float(h.current_price) if h.current_price else 0,
                        "current_value": float(h.current_value) if h.current_value else 0,
                        "gain_loss": float(h.current_value - h.total_cost) if (h.current_value and h.total_cost) else 0,
                        "gain_loss_percent": float((h.current_value - h.total_cost) / h.total_cost * 100) if (h.current_value and h.total_cost and h.total_cost != 0) else 0,
                        "broker": h.broker.value if h.broker else "unknown",
                    }
                    for h in holdings
                ],
                "recent_transactions": [
                    {
                        "symbol": t.asset.symbol if t.asset else "unknown",
                        "type": t.transaction_type.value if t.transaction_type else "unknown",
                        "quantity": float(t.quantity),
                        "price": float(t.price),
                        "date": t.transaction_date.isoformat() if t.transaction_date else None,
                        "broker": t.broker.value if t.broker else "unknown",
                    }
                    for t in transactions
                ],
            }

            execution_time = (time.time() - start_time) * 1000

            return self._create_output(
                success=True,
                data=data,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            logger.error(f"Portfolio agent error: {e}")
            execution_time = (time.time() - start_time) * 1000
            return self._create_output(
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )
