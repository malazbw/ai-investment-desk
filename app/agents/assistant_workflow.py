"""LangGraph workflow for routing and answering read-only investment questions."""

from decimal import Decimal
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.execution import execute_agents_parallel
from app.agents.router import AgentRouter
from app.agents.synthesis_agent import SynthesisAgent
from app.llm.client import LLMClient
from app.llm.context_builder import ContextBuilder


class AssistantWorkflowError(RuntimeError):
    """Raised when a workflow cannot produce an evidence-grounded answer."""


class UnknownAgentError(ValueError):
    """Raised when a request explicitly names an unregistered specialist."""


class AssistantState(TypedDict, total=False):
    user_message: str
    include_agents: list[str] | None
    llm_client: LLMClient
    db_factory: Callable[[], Any]
    selected_agents: list[BaseAgent]
    agent_outputs: list[AgentOutput]
    response: str


class AssistantWorkflow:
    """Route, execute relevant specialists, and synthesize only when needed."""

    def __init__(self, agent_router: AgentRouter) -> None:
        self.agent_router = agent_router
        graph = StateGraph(AssistantState)
        graph.add_node("route", self._route)
        graph.add_node("execute", self._execute)
        graph.add_node("direct_portfolio", self._answer_portfolio_lookup)
        graph.add_node("synthesize", self._synthesize)
        graph.add_edge(START, "route")
        graph.add_edge("route", "execute")
        graph.add_conditional_edges(
            "execute",
            self._needs_synthesis,
            {
                "direct_portfolio": "direct_portfolio",
                "synthesize": "synthesize",
            },
        )
        graph.add_edge("direct_portfolio", END)
        graph.add_edge("synthesize", END)
        self.graph = graph.compile()

    async def ainvoke(
        self,
        *,
        user_message: str,
        llm_client: LLMClient,
        db_factory: Callable[[], Any],
        include_agents: list[str] | None = None,
    ) -> AssistantState:
        return await self.graph.ainvoke(
            {
                "user_message": user_message,
                "llm_client": llm_client,
                "db_factory": db_factory,
                "include_agents": include_agents,
            }
        )

    async def _route(self, state: AssistantState) -> dict[str, Any]:
        requested = state.get("include_agents")
        if requested is not None:
            unknown = [name for name in requested if name not in self.agent_router.agents]
            if unknown:
                raise UnknownAgentError(
                    f"Unknown specialist name(s): {', '.join(unknown)}"
                )
            if not requested:
                raise UnknownAgentError("At least one specialist must be selected.")
            selected = [
                self.agent_router.agents[name] for name in dict.fromkeys(requested)
            ]
        else:
            selected = await self.agent_router.decide_agents(
                state["user_message"], state["llm_client"]
            )
        return {"selected_agents": selected}

    @staticmethod
    async def _execute(state: AssistantState) -> dict[str, Any]:
        outputs = await execute_agents_parallel(
            state["selected_agents"],
            AgentContext(
                user_message=state["user_message"],
                metadata={
                    "db_factory": state["db_factory"],
                    "llm_client": state["llm_client"],
                },
            ),
        )
        if not any(output.success for output in outputs):
            errors = "; ".join(
                f"{output.agent_name}: {output.error}"
                for output in outputs
                if output.error
            )
            raise AssistantWorkflowError(
                errors or "No specialist returned usable data."
            )
        return {"agent_outputs": outputs}

    @staticmethod
    def _needs_synthesis(state: AssistantState) -> str:
        selected = state["selected_agents"]
        if len(selected) == 1 and selected[0].name == "portfolio":
            return "direct_portfolio"
        return "synthesize"

    @staticmethod
    def _answer_portfolio_lookup(state: AssistantState) -> dict[str, str]:
        portfolio = next(
            (
                output
                for output in state["agent_outputs"]
                if output.agent_name == "portfolio" and output.success
            ),
            None,
        )
        if portfolio is None:
            raise AssistantWorkflowError(
                "Portfolio data could not be retrieved for this question."
            )

        data = portfolio.data
        holdings = data.get("holdings", [])
        if not holdings:
            return {"response": "No holdings are currently stored in your portfolio."}

        lines = [f"Your stored portfolio has {len(holdings)} holdings:"]
        for holding in holdings:
            symbol = holding.get("symbol", "Unknown asset")
            quantity = AssistantWorkflow._format_quantity(holding.get("quantity"))
            lines.append(f"- {symbol}: {quantity} units")

        summary = data.get("portfolio_summary", {})
        total_value = summary.get("total_value")
        currency = summary.get("currency")
        valuation_status = summary.get("valuation_status")
        if total_value is not None and currency:
            amount = Decimal(str(total_value))
            label = (
                "Partial stored value"
                if valuation_status == "partial"
                else "Total stored value"
            )
            lines.append(f"{label}: {currency} {amount:,.2f}.")
        if valuation_status == "partial":
            unpriced = summary.get("unpriced_holdings", [])
            if unpriced:
                lines.append(
                    "No usable stored price for: " + ", ".join(unpriced) + "."
                )
            else:
                lines.append("Some holdings have no usable stored price.")
        elif valuation_status == "mixed_currency":
            lines.append("A combined total is unavailable because currencies differ.")

        price_observations = sorted(
            {
                (holding.get("price_source"), (holding.get("price_date") or "")[:10])
                for holding in holdings
                if holding.get("price_source")
            }
        )
        for source, observed_date in price_observations:
            observation = (
                f" (observed {observed_date})" if observed_date else ""
            )
            if source == "virtual_broker":
                lines.append(
                    f"Virtual broker prices are sample data, not live quotes"
                    f"{observation}."
                )
            else:
                lines.append(f"Price source: {source}{observation}.")
        return {"response": "\n".join(lines)}

    @staticmethod
    def _format_quantity(value: Any) -> str:
        if value is None:
            return "unknown quantity"
        quantity = Decimal(str(value))
        return format(quantity.normalize(), "f")

    @staticmethod
    async def _synthesize(state: AssistantState) -> dict[str, Any]:
        context = ContextBuilder.build_context(state["agent_outputs"])
        output = await SynthesisAgent().execute(
            AgentContext(
                user_message=state["user_message"],
                metadata={
                    "llm_client": state["llm_client"],
                    "agent_outputs": context,
                },
            )
        )
        if not output.success:
            raise AssistantWorkflowError(
                "The specialist findings were collected but could not be synthesized."
            )
        return {
            "response": output.data["response"],
            "agent_outputs": [*state["agent_outputs"], output],
        }
