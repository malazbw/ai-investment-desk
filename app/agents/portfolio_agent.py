"""
Portfolio Agent - analyzes user's holdings via MCP tools (no direct DB access)
"""
import time
import json
from datetime import datetime
from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.assessment import build_assessment
from app.agents.findings import Finding, SourceRef, SourceType, EvidenceLevel
from typing import Dict, Any, Optional, List
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class PortfolioAgent(BaseAgent):
    """Agent that queries portfolio data ONLY via MCP tools"""

    def __init__(self):
        super().__init__(name="portfolio")

    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Get portfolio data for analysis via MCP tools ONLY.

        Args:
            context: Must contain 'mcp_client' in metadata

        Returns:
            AgentOutput with portfolio summary and holdings
        """
        start_time = time.time()
        logger.info(f"[PortfolioAgent] Starting execution")
        logger.info(f"[PortfolioAgent] Input message: {context.user_message}")

        try:
            mcp_client = context.metadata.get("mcp_client")
            if not mcp_client:
                raise ValueError("MCP client not provided in context")

            logger.info("[PortfolioAgent] Using MCP ONLY for portfolio data")

            # Get all portfolio data from MCP
            summary_result = await mcp_client.call_tool("get_portfolio_summary", {})
            if "error" in summary_result:
                raise ValueError(f"MCP error: {summary_result['error']}")

            holdings_result = await mcp_client.call_tool("get_all_holdings", {})
            if "error" in holdings_result:
                raise ValueError(f"MCP error: {holdings_result['error']}")

            transactions_result = await mcp_client.call_tool("get_recent_transactions", {"days": 30})
            if "error" in transactions_result:
                raise ValueError(f"MCP error: {transactions_result['error']}")

            # Extract data - all clean dicts from MCP
            summary_dict = summary_result
            holding_data = holdings_result.get("holdings", [])
            transactions_raw = transactions_result.get("transactions", [])

            logger.info(f"[PortfolioAgent] Got {len(holding_data)} holdings from MCP")

            # Extract structured findings
            findings: List[Finding] = []

            # Finding 1: Portfolio summary
            if summary_dict.get("total_value") is not None:
                findings.append(Finding(
                    claim=f"Total portfolio value: {summary_dict['total_value']} {summary_dict.get('currency', 'USD')}",
                    source=SourceRef(
                        source_type=SourceType.PORTFOLIO_DATA,
                        source_name="Portfolio Database",
                        url=None,
                        credibility_score=1.0,
                        fetched_at=datetime.utcnow()
                    ),
                    evidence_level=EvidenceLevel.PRIMARY,
                    confidence_score=1.0,
                    timestamp=datetime.utcnow(),
                    metadata={"status": summary_dict.get("valuation_status")}
                ))

                if summary_dict.get("total_gain_loss") is not None:
                    findings.append(Finding(
                        claim=f"Total gain/loss: {summary_dict['total_gain_loss']} ({summary_dict.get('total_gain_loss_percent')}%)",
                        source=SourceRef(
                            source_type=SourceType.PORTFOLIO_DATA,
                            source_name="Portfolio Database",
                            url=None,
                            credibility_score=1.0,
                            fetched_at=datetime.utcnow()
                        ),
                        evidence_level=EvidenceLevel.PRIMARY,
                        confidence_score=1.0,
                        timestamp=datetime.utcnow(),
                        metadata={"calculation": "from stored transactions and current prices"}
                    ))

            # Finding 2: Each holding
            for holding in holding_data:
                if holding.get("current_value") and Decimal(holding["current_value"]) > 0:
                    findings.append(Finding(
                        claim=f"{holding['symbol']}: {holding['quantity']} units @ {holding['current_price']} = {holding['current_value']}",
                        source=SourceRef(
                            source_type=SourceType.PRICE_DATA,
                            source_name="Portfolio Database",
                            url=None,
                            credibility_score=1.0,
                            fetched_at=datetime.utcnow()
                        ),
                        evidence_level=EvidenceLevel.PRIMARY,
                        confidence_score=1.0,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "symbol": holding["symbol"],
                            "gain_loss": holding.get("gain_loss"),
                            "gain_loss_percent": holding.get("gain_loss_percent"),
                        }
                    ))

            # Format assessment
            assessment_evidence = [
                f"{len(holding_data)} stored holdings; total value {summary_dict.get('total_value')} {summary_dict.get('currency', 'USD')}."
            ]

            if holding_data:
                biggest = max(holding_data, key=lambda h: float(h.get("current_value", 0) or 0), default=None)
                if biggest:
                    total_value = float(summary_dict.get("total_value", 0))
                    weight = (float(biggest["current_value"]) / total_value * 100) if total_value > 0 else 0
                    assessment_evidence.append(f"Largest position is {biggest['symbol']} at {weight:.2f}% of portfolio.")

            assessment_missing = [
                "The database may not include accounts held elsewhere.",
                "Investment goals and risk tolerance are not provided.",
            ]

            assessment_finding = f"Portfolio contains {len(holding_data)} holdings."

            # Format data
            data = {
                "findings": [f.to_dict() for f in findings],
                "assessment": build_assessment(
                    finding=assessment_finding,
                    evidence=assessment_evidence,
                    meaning="This describes the portfolio holdings retrieved via MCP tools.",
                    counterpoint="Actual portfolio may include other accounts or assets.",
                    confidence="High for accuracy of stored records; depends on data freshness.",
                    missing=assessment_missing,
                ),
                "portfolio_summary": summary_dict,
                "holdings": holding_data,
                "recent_transactions": transactions_raw,
            }

            execution_time = (time.time() - start_time) * 1000

            logger.info(f"[PortfolioAgent] Successfully processed {len(holding_data)} holdings via MCP")

            return self._create_output(
                success=True,
                data=data,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            logger.error(f"Portfolio agent error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"[PortfolioAgent] Failed after {execution_time:.2f}ms: {e}")
            return self._create_output(
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )
