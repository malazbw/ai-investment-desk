"""
Orchestrator Agent - coordinates other agents and synthesizes results
"""
import time
from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.portfolio_agent import PortfolioAgent
from app.agents.valuation_agent import ValuationAgent
from app.agents.execution import execute_agents_parallel
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator that runs all agents and synthesizes results"""

    def __init__(self):
        super().__init__(name="orchestrator")
        self.available_agents = {
            "portfolio": PortfolioAgent(),
            "valuation": ValuationAgent(),
        }

    def _decide_agents(self, message: str) -> List[BaseAgent]:
        """Run all available agents for complete context"""
        # Always run all agents - no keyword matching needed
        return list(self.available_agents.values())

    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Orchestrate agent execution and synthesis.

        Args:
            context: AgentContext with user message and database

        Returns:
            AgentOutput with synthesized results from all agents
        """
        start_time = time.time()

        try:
            user_message = context.user_message
            db = context.metadata.get("db")

            if not db:
                raise ValueError("Database session not provided in context")

            # Run all agents for complete context
            agents_to_run = self._decide_agents(user_message)
            logger.info(f"Orchestrator running agents: {[a.name for a in agents_to_run]}")

            # Execute agents in parallel
            agent_outputs = await execute_agents_parallel(agents_to_run, context)

            # Synthesize results
            synthesis = self._synthesize_outputs(user_message, agent_outputs)

            execution_time = (time.time() - start_time) * 1000

            return self._create_output(
                success=True,
                data={
                    "user_question": user_message,
                    "agents_executed": [a.agent_name for a in agent_outputs if a.success],
                    "agent_outputs": {a.agent_name: a.data for a in agent_outputs},
                    "synthesis": synthesis,
                    "execution_time_ms": execution_time,
                },
                execution_time_ms=execution_time,
            )

        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            execution_time = (time.time() - start_time) * 1000
            return self._create_output(
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    @staticmethod
    def _synthesize_outputs(question: str, outputs: List[AgentOutput]) -> Dict[str, Any]:
        """Synthesize all agent outputs into comprehensive answer"""
        synthesis = {
            "summary": "",
            "key_insights": [],
            "recommendations": [],
        }

        portfolio_data = None
        valuation_data = None

        # Extract data from agent outputs
        for output in outputs:
            if output.agent_name == "portfolio" and output.success:
                portfolio_data = output.data
            elif output.agent_name == "valuation" and output.success:
                valuation_data = output.data

        # Build comprehensive portfolio overview
        if portfolio_data:
            ps = portfolio_data.get('portfolio_summary', {})
            summary = f"Portfolio Overview:\n"
            summary += f"• Total Value: ${float(ps.get('total_value', 0)):,.2f}\n"
            summary += f"• Total Gain/Loss: ${float(ps.get('total_gain_loss', 0)):,.2f} "
            summary += f"({float(ps.get('total_gain_loss_percent', 0)):.2f}%)\n"
            summary += f"• Holdings: {ps.get('holdings_count', 0)}"

            synthesis["summary"] = summary

            # Add holdings ranked by performance
            holdings = portfolio_data.get("holdings", [])
            if holdings:
                sorted_holdings = sorted(
                    holdings,
                    key=lambda h: h.get("gain_loss_percent", 0),
                    reverse=True
                )
                for i, h in enumerate(sorted_holdings, 1):
                    rank_symbol = "🏆" if i == 1 else "🥈" if i == 2 else "🥉"
                    synthesis["key_insights"].append(
                        f"{rank_symbol} #{i}: {h['symbol']} - {h['gain_loss_percent']:.2f}% gain "
                        f"(${float(h.get('current_value', 0)):,.2f})"
                    )

        # Add valuation context
        if valuation_data:
            synthesis["key_insights"].append("")  # Spacing
            synthesis["key_insights"].append(f"📊 Valuation Analysis (Avg P/E: {valuation_data['average_pe']:.2f}):")

            for symbol, val in valuation_data.get("valuations", {}).items():
                judgment = val.get("valuation_judgment", "Fair")
                pe = val.get("pe_ratio", 0)
                judgment_emoji = "⬆️" if judgment == "Expensive" else "⬇️" if judgment == "Cheap" else "➡️"
                synthesis["key_insights"].append(
                    f"  {judgment_emoji} {symbol}: {judgment} (P/E: {pe:.2f})"
                )

            # Add recommendations based on valuation
            expensive = [s for s, v in valuation_data.get("valuations", {}).items()
                       if v.get("valuation_judgment") == "Expensive"]
            cheap = [s for s, v in valuation_data.get("valuations", {}).items()
                   if v.get("valuation_judgment") == "Cheap"]

            if expensive:
                synthesis["recommendations"].append(
                    f"📈 {', '.join(expensive)} trading at premium - monitor for pullback opportunities"
                )
            if cheap:
                synthesis["recommendations"].append(
                    f"📉 {', '.join(cheap)} trading at discount - consider adding on strength"
                )

        return synthesis
