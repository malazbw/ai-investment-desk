"""Create and invoke the main agent with the portfolio subagent as a tool."""
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

from app.agents.portfolio_subagent import create_portfolio_subagent
from app.agents.research_subagent import create_research_subagent_tool

logger = logging.getLogger(__name__)


def create_portfolio_subagent_tool(llm_model: Any):
    """Wrap the portfolio specialist so the main agent can call it as a tool."""
    portfolio_agent = create_portfolio_subagent(llm_model)

    @tool(
        "portfolio_subagent",
        description="Answer a question using the user's stored portfolio holdings.",
    )
    async def call_portfolio_subagent(query:str) -> str:
        result = await portfolio_agent.ainvoke({
            "messages": [{"role": "user", "content": query}]
        })
        messages = result.get("messages", [])
        if not messages:
            return "The portfolio agent returned no response."

        content = messages[-1].content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return str(content)

    return call_portfolio_subagent


def create_main_agent(llm_model: Any):
    """Create the main agent with portfolio and Tier 1 research specialists."""
    portfolio_tool = create_portfolio_subagent_tool(llm_model)
    research_tool = create_research_subagent_tool(llm_model)
    return create_agent(
        model=llm_model,
        tools=[portfolio_tool, research_tool],
        system_prompt="You are an investment assistant. Give clear answers based on the information available to you.",
        name="Main Investment Assistant",
    )


async def run_main_agent(llm_model: Any, user_query: str) -> dict[str, Any]:
    """Invoke the main agent and return its final text response."""
    logger.info("[MAIN_AGENT] Processing query: %s", user_query)
    try:
        main_agent = create_main_agent(llm_model)
        result = await main_agent.ainvoke({
            "messages": [{"role": "user", "content": user_query}]
        })
        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("Main agent returned no messages")

        content = messages[-1].content
        if isinstance(content, str):
            response = content
        elif isinstance(content, list):
            response = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            response = str(content)

        return {"success": True, "response": response}
    except Exception as exc:
        logger.exception("[MAIN_AGENT] Failed to process query")
        return {"success": False, "error": str(exc)}
