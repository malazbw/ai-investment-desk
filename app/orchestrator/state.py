"""
Orchestrator state definition for LangGraph workflow
"""
from typing import TypedDict, Annotated, Any
from operator import add


class OrchestratorState(TypedDict, total=False):
    """
    Shared state that flows through orchestrator nodes.

    Flow:
    1. route_node: Sets selected_agents
    2. execute_node: Sets agent_outputs (accumulated via reducer)
    3. synthesize_node: Sets final_response
    """
    # Input
    user_query: str

    # Route node output
    selected_agents: list[str]  # ["portfolio", "research", "discovery"]

    # Execute node output - accumulates findings from all agents
    agent_outputs: Annotated[dict[str, Any], add]  # {"research": {...}, "portfolio": {...}}

    # Synthesize node output
    final_response: str

    # Metadata (passed through, not modified)
    llm_client: Any
    db_factory: Any
    mcp_client: Any
