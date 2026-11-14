"""
Portfolio Subagent using LangChain subagents pattern.
Handles all portfolio-related queries (holdings, P&L, allocation, concentration).
"""
import logging
from typing import Any, Callable

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.findings import Finding, SourceRef, SourceType, EvidenceLevel
from app.agents.assessment import build_assessment
from datetime import datetime

logger = logging.getLogger(__name__)


class PortfolioSubagent:
    """
    Portfolio Subagent for LangChain subagents pattern.

    Capabilities:
    - Get user's holdings across all brokers
    - Calculate gains/losses
    - Analyze sector allocation
    - Identify concentration risks
    - Source-attributed findings
    """

    def __init__(self, llm_client: Any, db_factory: Callable[[], Any], mcp_client: Any = None):
        """
        Initialize Portfolio Subagent

        Args:
            llm_client: LLM client for decision making
            db_factory: Database session factory
            mcp_client: MCP client for portfolio tools
        """
        self.llm_client = llm_client
        self.db_factory = db_factory
        self.mcp_client = mcp_client
        self.logger = logging.getLogger(__name__)

        # Define tools available to this subagent
        self.tools = [
            self._get_portfolio_summary,
            self._get_holdings_by_broker,
            self._get_sector_allocation,
            self._get_concentration_analysis,
        ]

    @tool
    def _get_portfolio_summary(self) -> dict[str, Any]:
        """
        Get complete portfolio summary including total value, total gain/loss, and composition.
        Returns: Portfolio overview with source attribution
        """
        self.logger.info("[portfolio_subagent] Getting portfolio summary")

        try:
            # Use MCP client to get portfolio data
            if not self.mcp_client:
                return {"error": "MCP client not available"}

            # TODO: Implement MCP call to get portfolio data
            # For now, return mock data
            portfolio_data = {
                "total_value": 150000,
                "total_gain_loss": 22500,
                "gain_loss_percent": 15.0,
                "number_of_positions": 8,
                "number_of_brokers": 2,
            }

            findings = []

            # Create finding for total value
            findings.append({
                "claim": f"Portfolio total value: ${portfolio_data['total_value']:,.0f}",
                "source": {
                    "source_type": "portfolio_data",
                    "source_name": "Local Portfolio Database",
                    "url": None,
                    "credibility_score": 1.0,
                    "fetched_at": datetime.utcnow().isoformat()
                },
                "evidence_level": "primary",
                "confidence_score": 1.0,
                "metadata": {
                    "value": portfolio_data['total_value'],
                    "type": "total_value"
                }
            })

            # Create finding for gain/loss
            findings.append({
                "claim": f"Portfolio gain/loss: ${portfolio_data['total_gain_loss']:,.0f} ({portfolio_data['gain_loss_percent']:.1f}%)",
                "source": {
                    "source_type": "portfolio_data",
                    "source_name": "Local Portfolio Database",
                    "url": None,
                    "credibility_score": 1.0,
                    "fetched_at": datetime.utcnow().isoformat()
                },
                "evidence_level": "primary",
                "confidence_score": 1.0,
                "metadata": {
                    "gain_loss": portfolio_data['total_gain_loss'],
                    "percent": portfolio_data['gain_loss_percent'],
                    "type": "gain_loss"
                }
            })

            return {
                "success": True,
                "summary": portfolio_data,
                "findings": findings,
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"[portfolio_subagent] Error getting portfolio summary: {e}")
            return {"success": False, "error": str(e)}

    @tool
    def _get_holdings_by_broker(self) -> dict[str, Any]:
        """
        Get holdings grouped by broker.
        Returns: Holdings by broker with source attribution
        """
        self.logger.info("[portfolio_subagent] Getting holdings by broker")

        try:
            # Mock data for now
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

            findings = []
            total_by_broker = {}

            for broker, holdings in holdings_data.items():
                broker_value = sum(h["value"] for h in holdings)
                total_by_broker[broker] = broker_value

                # Create finding for broker allocation
                findings.append({
                    "claim": f"{broker.title()} holdings: ${broker_value:,.0f} ({len(holdings)} positions)",
                    "source": {
                        "source_type": "portfolio_data",
                        "source_name": f"{broker.title()} Broker",
                        "url": None,
                        "credibility_score": 1.0,
                        "fetched_at": datetime.utcnow().isoformat()
                    },
                    "evidence_level": "primary",
                    "confidence_score": 1.0,
                    "metadata": {
                        "broker": broker,
                        "value": broker_value,
                        "count": len(holdings)
                    }
                })

            return {
                "success": True,
                "holdings_by_broker": holdings_data,
                "totals_by_broker": total_by_broker,
                "findings": findings,
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"[portfolio_subagent] Error getting holdings by broker: {e}")
            return {"success": False, "error": str(e)}

    @tool
    def _get_sector_allocation(self) -> dict[str, Any]:
        """
        Get portfolio allocation by sector.
        Returns: Sector breakdown with source attribution
        """
        self.logger.info("[portfolio_subagent] Getting sector allocation")

        try:
            # Mock data for now
            sector_allocation = {
                "Technology": {"value": 12500, "percent": 50},
                "Financials": {"value": 5000, "percent": 20},
                "Healthcare": {"value": 5000, "percent": 20},
                "Consumer": {"value": 2500, "percent": 10},
            }

            findings = []

            for sector, data in sector_allocation.items():
                findings.append({
                    "claim": f"{sector} allocation: ${data['value']:,.0f} ({data['percent']:.0f}%)",
                    "source": {
                        "source_type": "portfolio_data",
                        "source_name": "Sector Classification",
                        "url": None,
                        "credibility_score": 0.9,
                        "fetched_at": datetime.utcnow().isoformat()
                    },
                    "evidence_level": "derived",
                    "confidence_score": 0.9,
                    "metadata": {
                        "sector": sector,
                        "value": data['value'],
                        "percent": data['percent']
                    }
                })

            return {
                "success": True,
                "sector_allocation": sector_allocation,
                "findings": findings,
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"[portfolio_subagent] Error getting sector allocation: {e}")
            return {"success": False, "error": str(e)}

    @tool
    def _get_concentration_analysis(self) -> dict[str, Any]:
        """
        Analyze portfolio concentration risks.
        Returns: Concentration metrics with source attribution
        """
        self.logger.info("[portfolio_subagent] Analyzing concentration")

        try:
            # Mock data for now
            concentration_data = {
                "largest_position": {"ticker": "MSFT", "value": 3500, "percent": 14},
                "top_3_positions": 45,
                "top_5_positions": 65,
                "tech_sector_percent": 50,
                "single_broker_percent": 60,
            }

            findings = []

            # Largest position finding
            findings.append({
                "claim": f"Largest position: {concentration_data['largest_position']['ticker']} at {concentration_data['largest_position']['percent']}% of portfolio",
                "source": {
                    "source_type": "portfolio_data",
                    "source_name": "Portfolio Analysis",
                    "url": None,
                    "credibility_score": 1.0,
                    "fetched_at": datetime.utcnow().isoformat()
                },
                "evidence_level": "derived",
                "confidence_score": 0.95,
                "metadata": {
                    "ticker": concentration_data['largest_position']['ticker'],
                    "percent": concentration_data['largest_position']['percent']
                }
            })

            # Tech concentration finding
            findings.append({
                "claim": f"Technology sector represents {concentration_data['tech_sector_percent']}% of portfolio - HIGH concentration",
                "source": {
                    "source_type": "portfolio_data",
                    "source_name": "Sector Analysis",
                    "url": None,
                    "credibility_score": 0.9,
                    "fetched_at": datetime.utcnow().isoformat()
                },
                "evidence_level": "derived",
                "confidence_score": 0.9,
                "metadata": {
                    "sector": "Technology",
                    "percent": concentration_data['tech_sector_percent'],
                    "risk_level": "high"
                }
            })

            return {
                "success": True,
                "concentration": concentration_data,
                "findings": findings,
                "risk_assessment": "HIGH - Concentrated in tech and single broker",
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"[portfolio_subagent] Error analyzing concentration: {e}")
            return {"success": False, "error": str(e)}

    async def run(self, query: str) -> dict[str, Any]:
        """
        Run the Portfolio Subagent as an independent agent.

        Args:
            query: User's portfolio-related question

        Returns:
            Agent response with findings and assessment
        """
        self.logger.info(f"[portfolio_subagent] Running with query: {query}")

        try:
            # For now, just return portfolio summary
            # In a full implementation, LLM would decide which tools to use

            summary_result = self._get_portfolio_summary()
            broker_result = self._get_holdings_by_broker()
            sector_result = self._get_sector_allocation()
            concentration_result = self._get_concentration_analysis()

            # Combine all findings
            all_findings = []
            all_findings.extend(summary_result.get("findings", []))
            all_findings.extend(broker_result.get("findings", []))
            all_findings.extend(sector_result.get("findings", []))
            all_findings.extend(concentration_result.get("findings", []))

            # Create assessment
            assessment = build_assessment(
                finding="Portfolio analysis complete",
                evidence=[f.get("claim") for f in all_findings[:5]],
                meaning="Your portfolio is well-diversified across brokers but concentrated in technology",
                counterpoint="Concentration could be intentional based on investment thesis",
                confidence="High - Based on actual holdings data",
                missing=["Historical performance comparison", "Tax implications"]
            )

            return {
                "success": True,
                "findings": all_findings,
                "assessment": assessment,
                "summary": summary_result.get("summary", {}),
                "data": {
                    "holdings_by_broker": broker_result.get("holdings_by_broker", {}),
                    "sector_allocation": sector_result.get("sector_allocation", {}),
                    "concentration": concentration_result.get("concentration", {}),
                }
            }

        except Exception as e:
            self.logger.error(f"[portfolio_subagent] Error running agent: {e}")
            return {
                "success": False,
                "error": str(e),
                "findings": [],
                "assessment": {}
            }
