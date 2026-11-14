"""
Main Agent following LangChain subagents pattern.
https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

Orchestrates all subagents (Portfolio, Research, etc.).
Routes queries to appropriate subagent(s).
Synthesizes results into final answer.
"""
import logging
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.portfolio_subagent_v2 import create_portfolio_subagent_tool

logger = logging.getLogger(__name__)


def create_main_agent(llm_client: Any):
    """
    Create Main Agent that orchestrates all subagents.

    This agent:
    - Routes user queries to appropriate subagents
    - Can call multiple subagents if needed
    - Synthesizes results into coherent response

    Args:
        llm_client: LLM client (Ollama, Claude, etc.)

    Returns:
        AgentExecutor for main agent
    """
    logger.info("[main_agent] Creating Main Agent")

    # Create tools (subagents)
    portfolio_tool = create_portfolio_subagent_tool(llm_client)

    # TODO: Create Research Subagent Tool
    # research_tool = create_research_subagent_tool(llm_client)

    # Tools available to main agent
    tools = [
        portfolio_tool,
        # research_tool,  # TODO: Add when research subagent is created
    ]

    # Define system prompt for main agent
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an investment advisor AI assistant.

You have access to multiple specialist subagents:
1. portfolio_subagent - For questions about the user's portfolio (holdings, allocation, concentration, P&L)
2. research_subagent - For questions about company valuations and stock analysis (TODO)

Based on the user's question, decide which subagent(s) to call:
- If asking about "my portfolio", "my holdings", "allocation", "concentration" → use portfolio_subagent
- If asking about "should I buy", "what's the P/E", "is this stock good" → use research_subagent (TODO)
- If asking about both aspects → call both subagents

After getting results from subagents, synthesize them into a clear, helpful response.
Provide actionable advice based on the combined information."""
        ),
        MessagesPlaceholder(variable_name="messages"),
    ])

    # Create tool-calling agent
    agent = create_tool_calling_agent(llm_client, tools, prompt)

    # Create agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
    )

    return agent_executor


async def run_main_agent(llm_client: Any, user_query: str) -> dict[str, Any]:
    """
    Run the Main Agent with a user query.

    Args:
        llm_client: LLM client
        user_query: User's investment question

    Returns:
        Agent response with answer
    """
    logger.info(f"[main_agent] Running with query: {user_query}")

    try:
        # Create main agent
        agent_executor = create_main_agent(llm_client)

        # Run agent
        result = agent_executor.invoke({"input": user_query})

        logger.info("[main_agent] Agent execution completed")

        return {
            "success": True,
            "query": user_query,
            "response": result.get("output", "No response generated"),
        }

    except Exception as e:
        logger.error(f"[main_agent] Error: {e}")
        return {
            "success": False,
            "query": user_query,
            "error": str(e),
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

"""
# In FastAPI routes:

@router.post("/chat/message")
async def chat_message(request: ChatRequest):
    # Initialize LLM client
    llm_client = ...  # Ollama, Claude, etc.

    # Run main agent
    result = await run_main_agent(llm_client, request.message)

    return ChatResponse(
        response=result["response"],
        success=result["success"],
    )

# Example queries:
# "What is my portfolio allocation?"
#   → Calls portfolio_subagent
#   → Returns sector breakdown, broker allocation
#
# "What's the market situation?"
#   → Could call research_subagent (TODO)
#   → Returns macro context
#
# "My portfolio is down 15%. Should I buy Tesla?"
#   → Calls both portfolio_subagent + research_subagent
#   → Returns: "Based on your portfolio context (50% tech concentration)
#               and Tesla valuation (P/E 45), I recommend..."
"""
