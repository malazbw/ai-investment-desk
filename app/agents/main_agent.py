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
from app.agents.research_subagent import create_research_subagent_tool

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
    logger.info("\n" + "="*80)
    logger.info("[MAIN_AGENT] ✓ STARTED")
    logger.info(f"[MAIN_AGENT] Query: {user_query}")
    logger.info("="*80)

    try:
        # Create tools (subagents)
        logger.info("[MAIN_AGENT] Creating portfolio subagent tool...")
        portfolio_tool = create_portfolio_subagent_tool(llm_model)
        logger.info("[MAIN_AGENT] ✓ Portfolio subagent tool created")

        logger.info("[MAIN_AGENT] Creating research subagent tool...")
        research_tool = create_research_subagent_tool(llm_model)
        logger.info("[MAIN_AGENT] ✓ Research subagent tool created")

        # Tools available to main agent
        tools = [portfolio_tool, research_tool]
        logger.info(f"[MAIN_AGENT] Tools available: {len(tools)}")

        # System prompt for main agent
        system_prompt = """You are an investment advisor AI assistant.

You have access to specialist tools:
- portfolio_subagent: Answer questions about the user's portfolio (holdings, allocation, concentration, P&L)
- research_subagent: Answer questions about company valuation metrics (P/E, EPS, dividend, market cap, 52-week range)

Route queries intelligently to the appropriate subagent(s) based on user intent:
- If asking about "my portfolio", "my holdings", "my allocation" → use portfolio_subagent
- If asking about "valuation", "P/E ratio", "earnings", "dividend", "market cap" for specific stocks → use research_subagent
- If asking about multiple topics → use both subagents and synthesize results

Synthesize the results into a clear, helpful response."""

        # Create agent using LangChain
        logger.info("[MAIN_AGENT] Creating LangChain agent with create_agent()...")
        agent = create_agent(
            model=llm_model,
            tools=tools,
            system_prompt=system_prompt,
        )
        logger.info("[MAIN_AGENT] ✓ Agent created successfully")

        # Run agent - create_agent returns a CompiledStateGraph
        logger.info("[MAIN_AGENT] Invoking agent with query...")
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_query}]})
        logger.info("[MAIN_AGENT] ✓ Agent execution completed")

        logger.info("[MAIN_AGENT] ✓ SUCCESS")
        logger.info("="*80)

        return {
            "success": True,
            "response": result.get("output", str(result)),
        }

    except Exception as e:
        logger.error(f"[MAIN_AGENT] ✗ ERROR: {e}", exc_info=True)
        logger.error("="*80)
        return {
            "success": False,
            "error": str(e),
        }
