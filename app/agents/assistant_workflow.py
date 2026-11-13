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
    mcp_client: Any  # MCPClient for portfolio tools
    selected_agents: list[BaseAgent]
    agent_outputs: list[AgentOutput]
    response: str


class AssistantWorkflow:
    """Route, execute relevant specialists, and synthesize results."""

    def __init__(self, agent_router: AgentRouter, mcp_client: Any = None) -> None:
        self.agent_router = agent_router
        self.mcp_client = mcp_client
        graph = StateGraph(AssistantState)
        graph.add_node("route", self._route)
        graph.add_node("execute", self._execute)
        graph.add_node("synthesize", self._synthesize)
        graph.add_edge(START, "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", "synthesize")
        graph.add_edge("synthesize", END)
        self.graph = graph.compile()

    async def ainvoke(
        self,
        *,
        user_message: str,
        llm_client: LLMClient,
        db_factory: Callable[[], Any],
        mcp_client: Any = None,
        include_agents: list[str] | None = None,
    ) -> AssistantState:
        return await self.graph.ainvoke(
            {
                "user_message": user_message,
                "llm_client": llm_client,
                "db_factory": db_factory,
                "mcp_client": mcp_client or self.mcp_client,
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
                    "mcp_client": state.get("mcp_client"),
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
