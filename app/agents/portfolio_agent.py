"""
Portfolio Agent - analyzes user's holdings and portfolio
"""
import time
from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.assessment import build_assessment
from app.models import Price
from app.services import PortfolioService
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
from decimal import Decimal

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
        logger.info(f"[PortfolioAgent] Starting execution")
        logger.info(f"[PortfolioAgent] Input message: {context.user_message}")

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

            holding_data = []
            for holding in holdings:
                asset = holding.asset
                latest_price = (
                    db.query(Price)
                    .filter(Price.asset_id == asset.id)
                    .order_by(Price.price_date.desc(), Price.id.desc())
                    .first()
                    if asset
                    else None
                )
                holding_data.append(
                    {
                        "symbol": asset.symbol if asset else "unknown",
                        "name": asset.name if asset else "unknown",
                        "quantity": str(holding.quantity),
                        "average_cost": str(holding.average_cost),
                        "total_cost": str(holding.total_cost),
                        "current_price": (
                            str(holding.current_price)
                            if holding.current_price is not None
                            else None
                        ),
                        "current_value": (
                            str(holding.current_value)
                            if holding.current_value is not None
                            else None
                        ),
                        "gain_loss": (
                            str(holding.gain_loss)
                            if holding.gain_loss is not None else None
                        ),
                        "gain_loss_percent": (
                            str(holding.gain_loss_percent)
                            if holding.gain_loss_percent is not None else None
                        ),
                        "broker": (
                            holding.broker.value if holding.broker else "unknown"
                        ),
                        "price_source": latest_price.source if latest_price else None,
                        "price_currency": (
                            holding.price_currency if latest_price else None
                        ),
                        "price_date": (
                            latest_price.price_date.isoformat()
                            if latest_price
                            else None
                        ),
                        "price_freshness": holding.price_freshness,
                    }
                )

            priced_values = [
                holding
                for holding in holding_data
                if holding["current_value"] is not None
                and holding["price_currency"] is not None
                and Decimal(holding["current_value"]) > 0
            ]
            valuation_currencies = {
                holding["price_currency"] for holding in priced_values
            }
            valued_holdings = (
                priced_values if len(valuation_currencies) <= 1 else []
            )
            total_valued = sum(
                (Decimal(str(holding["current_value"])) for holding in valued_holdings),
                Decimal("0"),
            )
            largest_holding = max(
                valued_holdings,
                key=lambda holding: Decimal(str(holding["current_value"])),
                default=None,
            )
            largest_weight = (
                Decimal(str(largest_holding["current_value"]))
                / total_valued
                * Decimal("100")
                if largest_holding and total_valued
                else None
            )
            price_sources = sorted(
                {
                    holding["price_source"] or "unknown"
                    for holding in holding_data
                    if holding["current_value"] is not None
                }
            )
            assessment_evidence = [
                (
                    f"{len(holding_data)} stored holdings; total value "
                    f"{summary.total_value} {summary.currency}."
                    if summary.total_value is not None
                    else (
                        f"{len(holding_data)} stored holdings; no combined total "
                        "is available because currencies are mixed."
                    )
                )
            ]
            if largest_holding and largest_weight is not None:
                assessment_evidence.append(
                    f"Largest stored position is {largest_holding['symbol']} "
                    f"at {largest_weight:.2f}% of valued holdings."
                )
            if valued_holdings:
                assessment_evidence.append(
                    "Price sources: " + ", ".join(price_sources) + "."
                )
            has_sample_prices = "virtual_broker" in price_sources
            assessment_missing = [
                "The database may not include accounts or assets held elsewhere.",
                "Investment goals, time horizon, and risk tolerance are not provided.",
            ]
            if has_sample_prices:
                assessment_missing.append(
                    "A virtual_broker price is sample data, not a live market quote."
                )
            if summary.valuation_status == "partial":
                assessment_missing.append(
                    "Some holdings have no usable stored price, so the portfolio "
                    "gain/loss is unavailable and total value is partial."
                )
            elif summary.valuation_status == "mixed_currency":
                assessment_missing.append(
                    "Holdings or prices use different currencies; no combined "
                    "portfolio value or gain/loss is calculated."
                )
            assessment_finding = (
                f"The stored portfolio contains {len(holding_data)} holdings."
                if holding_data
                else "No holdings are stored in the portfolio."
            )
            if largest_holding and largest_weight is not None:
                assessment_finding += (
                    f" {largest_holding['symbol']} is the largest at "
                    f"{largest_weight:.2f}% of valued holdings."
                )

            # Format data
            data = {
                "portfolio_summary": {
                    "total_value": (
                        str(summary.total_value)
                        if summary.total_value is not None
                        else None
                    ),
                    "total_cost": (
                        str(summary.total_cost)
                        if summary.total_cost is not None
                        else None
                    ),
                    "total_gain_loss": (
                        str(summary.total_gain_loss)
                        if summary.total_gain_loss is not None
                        else None
                    ),
                    "total_gain_loss_percent": (
                        str(summary.total_gain_loss_percent)
                        if summary.total_gain_loss_percent is not None
                        else None
                    ),
                    "cash_value": str(summary.cash_value),
                    "currency": summary.currency,
                    "valuation_status": summary.valuation_status,
                    "unpriced_holdings": summary.unpriced_holdings,
                },
                "holdings": holding_data,
                "recent_transactions": [
                    {
                        "symbol": t.asset.symbol if t.asset else "unknown",
                        "type": t.transaction_type.value if t.transaction_type else "unknown",
                        "quantity": str(t.quantity),
                        "price": str(t.price),
                        "date": t.transaction_date.isoformat() if t.transaction_date else None,
                        "broker": t.broker.value if t.broker else "unknown",
                    }
                    for t in transactions
                ],
                "assessment": build_assessment(
                    finding=assessment_finding,
                    evidence=assessment_evidence,
                    meaning=(
                        "This describes only the holdings and price records stored "
                        "in this desk; it is not a complete personal financial picture."
                    ),
                    counterpoint=(
                        "Concentration within these records may overstate or understate "
                        "your overall exposure if other accounts or assets are missing."
                    ),
                    confidence=(
                        "High for arithmetic on stored records; low for completeness "
                        "or current market value when prices are sample or stale."
                    ),
                    missing=assessment_missing,
                ),
            }

            execution_time = (time.time() - start_time) * 1000

            logger.info(f"[PortfolioAgent] Successfully processed {len(holdings)} holdings")
            logger.debug(f"[PortfolioAgent] Output data keys: {list(data.keys())}")

            return self._create_output(
                success=True,
                data=data,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            logger.error(f"Portfolio agent error: {e}")
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"[PortfolioAgent] Failed after {execution_time:.2f}ms: {e}")
            return self._create_output(
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )
