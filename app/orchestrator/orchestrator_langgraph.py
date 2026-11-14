"""
LangGraph-based orchestrator for multi-agent workflow (refactored).
Routes queries to appropriate agents using LLM intelligence, not keyword matching.
"""
import json
import logging
from typing import Any, Callable

from langgraph.graph import StateGraph, END, START

from app.orchestrator.state import OrchestratorState
from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.execution import execute_agents_parallel
from app.llm.client import LLMClient
from app.llm.context_builder import ContextBuilder
from app.agents.synthesis_agent import SynthesisAgent

logger = logging.getLogger(__name__)


class OrchestratorLangGraph:
    """
    LangGraph-based multi-agent orchestrator.

    Flow:
    1. route_node: LLM decides which agents to run (no keyword matching)
    2. execute_node: Run selected agents in parallel
    3. synthesize_node: LLM combines findings into final answer
    """

    ROUTING_SYSTEM_PROMPT = """You are an intelligent query router for an investment research system.

Based on the user's question, decide which specialist agents should handle it.

Available specialists:
- portfolio: User's holdings, positions, transactions, portfolio composition, gains/losses
- research: Company research - valuation metrics (P/E, EPS, dividends, market cap), financial analysis

Choose ONLY the specialists whose information is materially relevant to answer the question.
Do NOT choose all specialists automatically. Be precise.

Respond ONLY with a JSON object on a single line:
{"agents": ["portfolio"]}

Examples:
- "What do I own?" → {"agents": ["portfolio"]}
- "What is Microsoft's P/E ratio?" → {"agents": ["research"]}
- "Does Apple pay dividends?" → {"agents": ["research"]}
- "Should I buy TSLA?" → {"agents": ["portfolio", "research"]}
"""

    def __init__(self, agents: dict[str, BaseAgent]) -> None:
        """
        Initialize orchestrator with available agents

        Args:
            agents: Dict mapping agent names to BaseAgent instances
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
        Route: Use LLM to decide which agents to run (no keyword matching).
        LLM intelligently analyzes the query against available agents.
        """
        self.logger.info("[ROUTE] Using LLM to decide agents")

        llm_client = state["llm_client"]
        user_query = state["user_query"]
        available_names = list(self.agents.keys())

        try:
            # Use LLM to decide agents (no keyword matching)
            response = await llm_client.analyze(
                user_message=user_query,
                system_prompt=self.ROUTING_SYSTEM_PROMPT,
                context={"available_specialists": available_names},
            )

            # Parse routing decision
            try:
                routing_data = json.loads(response)
                selected_names = routing_data.get("agents", [])
            except json.JSONDecodeError:
                self.logger.warning(f"[ROUTE] Invalid JSON from LLM, defaulting to portfolio: {response}")
                selected_names = ["portfolio"]

            # Validate agent names
            selected_names = [name for name in selected_names if name in self.agents]
            if not selected_names:
                selected_names = ["portfolio"]

            selected_agents = [self.agents[name] for name in dict.fromkeys(selected_names)]

            self.logger.info(f"[ROUTE] Selected agents: {[a.name for a in selected_agents]}")

            return {"selected_agents": selected_agents}

        except Exception as e:
            self.logger.error(f"[ROUTE] Error during routing: {e}")
            # Fallback to portfolio agent
            return {"selected_agents": [self.agents.get("portfolio")] if "portfolio" in self.agents else []}

    @staticmethod
    async def _execute(state: OrchestratorState) -> dict[str, Any]:
        """
        Execute: Run selected agents in parallel.
        Accumulates findings from all agents into agent_outputs dict.
        """
        logger.info(f"[EXECUTE] Running {len(state.get('selected_agents', []))} agents in parallel")

        selected_agents = state.get("selected_agents", [])

        if not selected_agents:
            logger.warning("[EXECUTE] No agents selected")
            return {"agent_outputs": {}}

        context = AgentContext(
            user_message=state["user_query"],
            metadata={
                "db_factory": state["db_factory"],
                "llm_client": state["llm_client"],
                "mcp_client": state.get("mcp_client"),
            },
        )

        agent_outputs = await execute_agents_parallel(selected_agents, context)

        # Convert list of AgentOutput to dict indexed by agent name
        output_dict = {}
        for output in agent_outputs:
            output_dict[output.agent_name] = output.data

        logger.info(f"[EXECUTE] Agents completed")

        return {"agent_outputs": output_dict}

    @staticmethod
    async def _synthesize(state: OrchestratorState) -> dict[str, Any]:
        """
        Synthesize: Use LLM to combine agent findings into final answer.
        """
        logger.info("[SYNTHESIZE] Combining findings")

        # Build context from agent outputs
        agent_outputs_list = []
        for agent_name, output_data in state.get("agent_outputs", {}).items():
            agent_outputs_list.append(AgentOutput(
                agent_name=agent_name,
                success=True,
                data=output_data,
                error=None,
                execution_time_ms=0
            ))

        context = ContextBuilder.build_context(agent_outputs_list)

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
            response = "Could not synthesize findings. Please try again."
        else:
            response = synthesis_output.data.get("response", "No response generated")

        logger.info("[SYNTHESIZE] Complete")

        return {
            "final_response": response,
        }
