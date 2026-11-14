"""
Main Agent following LangChain subagents pattern.
https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

Orchestrates all subagents (Portfolio, Research, etc.).
Routes queries to appropriate subagent(s).
Synthesizes results into final answer.
"""
import logging
from typing import Any

from langchain.agents import create_agent
from app.agents.portfolio_subagent import create_portfolio_subagent_tool

logger = logging.getLogger(__name__)


async def run_main_agent(llm_model: Any, user_query: str) -> dict[str, Any]:
    """
    Run Main Agent that orchestrates all subagents.

    Args:
        llm_model: LangChain chat model (from provider.get_langchain_model())
        user_query: User's investment question

    Returns:
        Agent response with answer
    """
    logger.info(f"[main_agent] Processing query: {user_query}")

    try:
        # Create tools (subagents)
        portfolio_tool = create_portfolio_subagent_tool(llm_model)

        # Tools available to main agent
        tools = [portfolio_tool]

        # System prompt for main agent
        system_prompt = """You are an investment advisor AI assistant.

You have access to specialist tools:
- portfolio_subagent: Answer questions about the user's portfolio (holdings, allocation, concentration, P&L)

When asked portfolio questions, use the portfolio_subagent tool.
Synthesize the results into a clear, helpful response."""

        # Create agent using LangChain
        agent = create_agent(
            model=llm_model,
            tools=tools,
            system_prompt=system_prompt,
        )

        logger.info("[main_agent] Created agent, invoking with query")

        # Run agent - create_agent returns a CompiledStateGraph
        result = await agent.ainvoke({"input": user_query})

        logger.info("[main_agent] Agent execution completed")

        return {
            "success": True,
            "response": result.get("output", str(result)),
        }

    except Exception as e:
        logger.error(f"[main_agent] Error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }
