"""Synthesis agent that turns specialist outputs into a final chat response."""

import time
from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.llm.client import LLMClient
from app.llm.prompts import SystemPrompts


class SynthesisAgent(BaseAgent):
    """Combine specialist findings, conflicts, and limitations for the user."""

    def __init__(self) -> None:
        super().__init__(name="synthesis")

    async def execute(self, context: AgentContext) -> AgentOutput:
        started = time.monotonic()
        client = context.metadata.get("llm_client")
        agent_outputs = context.metadata.get("agent_outputs")
        if not isinstance(client, LLMClient):
            return self._create_output(
                False, {}, "LLM client not provided to synthesis agent"
            )
        if not isinstance(agent_outputs, dict):
            return self._create_output(
                False, {}, "Specialist agent outputs not provided to synthesis agent"
            )

        market_research = agent_outputs.get("market_research")
        detailed_report = (
            market_research.get("on_demand_analysis")
            if isinstance(market_research, dict)
            else None
        )
        if (
            isinstance(detailed_report, str)
            and detailed_report.startswith("1. Executive summary")
            and "\n8. Key risks" in detailed_report
        ):
            return self._create_output(
                True,
                {
                    "response": detailed_report,
                    "specialists_considered": [
                        name for name in agent_outputs if not name.startswith("_")
                    ],
                    "warnings": agent_outputs.get("_errors", []),
                },
                execution_time_ms=(time.monotonic() - started) * 1000,
            )

        try:
            response = await client.analyze(
                user_message=context.user_message,
                system_prompt=SystemPrompts.SYNTHESIS_ANALYST,
                context=agent_outputs,
            )
            return self._create_output(
                True,
                {
                    "response": response,
                    "specialists_considered": [
                        name for name in agent_outputs if not name.startswith("_")
                    ],
                    "warnings": agent_outputs.get("_errors", []),
                },
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:
            self.logger.exception("Synthesis agent failed")
            return self._create_output(
                False,
                {},
                str(exc),
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
