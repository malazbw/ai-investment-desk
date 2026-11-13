"""
LangGraph-based orchestrator for multi-agent workflow.
Routes queries to appropriate agents using LLM intelligence, not keyword matching.
"""
import logging
from typing import Any, Callable

from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.execution import execute_agents_parallel
from app.llm.client import LLMClient
from app.llm.context_builder import ContextBuilder
from app.agents.synthesis_agent import SynthesisAgent

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict, total=False):
    """State passed through LangGraph workflow"""
    user_query: str
    db_factory: Callable[[], Any]
    llm_client: LLMClient
    mcp_client: Any

    # Agent selection
    selected_agents: list[BaseAgent]

    # Agent execution
    agent_outputs: list[AgentOutput]

    # Final response
    response: str


class Orchestrator:
    """
    Multi-agent orchestrator using LangGraph.

    Flow:
    1. Route: LLM decides which agents to run (no keyword matching)
    2. Execute: Run selected agents in parallel
    3. Synthesize: LLM combines findings into final answer
    """

    ROUTING_SYSTEM_PROMPT = """You are an intelligent query router for an investment research system.

Based on the user's question, decide which specialist agents should handle it.

Available specialists:
- portfolio: User's holdings, positions, transactions, portfolio composition, gains/losses
- research: Company research - valuation metrics (P/E, EPS, dividends, market cap), financial analysis

Choose ONLY the specialists whose information is materially relevant to answer the question.
Do not choose all specialists automatically. Be precise.

Respond ONLY with a JSON object on a single line:
{"agents": ["portfolio"]}

Examples:
- "What do I own?" → {"agents": ["portfolio"]}
- "What is my total value?" → {"agents": ["portfolio"]}
- "What is Microsoft's P/E ratio?" → {"agents": ["research"]}
- "Does Apple pay dividends?" → {"agents": ["research"]}
- "Should I buy TSLA?" → {"agents": ["portfolio", "research"]}
"""

    def __init__(self, agents: dict[str, BaseAgent]) -> None:
        """
        Initialize orchestrator with available agents

        Args:
            agents: Dict mapping agent names to BaseAgent instances
                   e.g., {"portfolio": PortfolioAgent(), "research": ResearchAgent()}
        """
        self.agents = agents
        self.logger = logger

        # Build LangGraph workflow
        graph = StateGraph(OrchestratorState)
        graph.add_node("route", self._route)
        graph.add_node("execute", self._execute)
        graph.add_node("synthesize", self._synthesize)

        graph.add_edge(START, "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", "synthesize")
        graph.add_edge("synthesize", END)

        self.graph = graph.compile()
        self.logger.info(f"Orchestrator initialized with agents: {list(agents.keys())}")

    async def ainvoke(
        self,
        *,
        user_query: str,
        llm_client: LLMClient,
        db_factory: Callable[[], Any],
        mcp_client: Any = None,
    ) -> OrchestratorState:
        """
        Run the orchestrator workflow

        Args:
            user_query: The user's question
            llm_client: LLM client for routing and synthesis
            db_factory: Database session factory
            mcp_client: Optional MCP client for portfolio tools

        Returns:
            Final orchestrator state with response
        """
        self.logger.info(f"[ORCHESTRATOR] Processing: {user_query[:100]}...")

        result = await self.graph.ainvoke({
            "user_query": user_query,
            "llm_client": llm_client,
            "db_factory": db_factory,
            "mcp_client": mcp_client,
        })

        self.logger.info(f"[ORCHESTRATOR] Complete")
        return result

    async def _route(self, state: OrchestratorState) -> dict[str, Any]:
        """
        Route: Use LLM to decide which agents to run
        """
        self.logger.info("[ROUTE] Deciding which agents to use...")

        llm_client = state["llm_client"]
        user_query = state["user_query"]
        available_names = list(self.agents.keys())

        # Use LLM to decide agents (no keyword matching)
        response = await llm_client.analyze(
            user_message=user_query,
            system_prompt=self.ROUTING_SYSTEM_PROMPT,
            context={"available_specialists": available_names},
        )

        # Parse routing decision
        import json
        try:
            routing_data = json.loads(response)
            selected_names = routing_data.get("agents", [])
        except (json.JSONDecodeError, TypeError):
            self.logger.warning(f"[ROUTE] Invalid routing response, using portfolio: {response}")
            selected_names = ["portfolio"]

        # Validate and get agent instances
        selected_names = [name for name in selected_names if name in self.agents]
        if not selected_names:
            selected_names = ["portfolio"]

        selected_agents = [self.agents[name] for name in dict.fromkeys(selected_names)]

        self.logger.info(f"[ROUTE] Selected agents: {[a.name for a in selected_agents]}")

        return {"selected_agents": selected_agents}

    @staticmethod
    async def _execute(state: OrchestratorState) -> dict[str, Any]:
        """
        Execute: Run selected agents in parallel
        """
        logger.info(f"[EXECUTE] Running {len(state['selected_agents'])} agents in parallel...")

        context = AgentContext(
            user_message=state["user_query"],
            metadata={
                "db_factory": state["db_factory"],
                "llm_client": state["llm_client"],
                "mcp_client": state.get("mcp_client"),
            },
        )

        agent_outputs = await execute_agents_parallel(
            state["selected_agents"],
            context,
        )

        logger.info(f"[EXECUTE] Agents completed")

        return {"agent_outputs": agent_outputs}

    @staticmethod
    async def _synthesize(state: OrchestratorState) -> dict[str, Any]:
        """
        Synthesize: Use LLM to combine agent findings into final answer
        """
        logger.info("[SYNTHESIZE] Combining findings...")

        # Build context from agent outputs
        context = ContextBuilder.build_context(state["agent_outputs"])

        # Use synthesis agent to create final answer
        synthesis_output = await SynthesisAgent().execute(
            AgentContext(
                user_message=state["user_query"],
                metadata={
                    "llm_client": state["llm_client"],
                    "agent_outputs": context,
                },
            )
        )

        if not synthesis_output.success:
            logger.error(f"[SYNTHESIZE] Synthesis failed: {synthesis_output.error}")
            # Fallback: return raw context
            response = "Could not synthesize findings. Please try again."
        else:
            response = synthesis_output.data.get("response", "No response generated")

        logger.info("[SYNTHESIZE] Complete")

        return {
            "response": response,
            "agent_outputs": [*state["agent_outputs"], synthesis_output],
        }
