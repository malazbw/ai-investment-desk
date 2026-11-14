"""
Test LangChain agent with Gemini (supports tool calling).
"""
import asyncio
import logging
import os

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# SIMPLE TOOLS
# ============================================================================

@tool
def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"The weather in {location} is sunny and 72°F."


@tool
def get_time() -> str:
    """Get the current time."""
    return "The current time is 3:45 PM."


@tool
def get_portfolio_summary() -> str:
    """Get user's portfolio summary."""
    return """
Portfolio Summary:
- Total Value: $150,000
- Total Gain/Loss: $22,500 (+15%)
- Holdings: 8 positions across 2 brokers
- Allocation: 50% Technology, 20% Financials, 20% Healthcare, 10% Consumer
"""


# ============================================================================
# HELPERS
# ============================================================================

def message_text(message) -> str:
    """Return the text of a message, whether content is a str or a list of blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


# ============================================================================
# TEST AGENT
# ============================================================================

async def test_gemini_agent():
    """Test agent with Gemini."""
    logger.info("Testing LangChain Agent with Gemini...")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return False

    try:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            temperature=0.7,
        )

        tools = [get_weather, get_time, get_portfolio_summary]

        logger.info("Creating agent with create_agent()...")
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt="""You are a helpful assistant with access to tools:
- get_weather: Get weather for a location
- get_time: Get current time
- get_portfolio_summary: Get user's portfolio information

Use these tools to answer user questions accurately.""",
        )
        logger.info("✓ Agent created successfully")

        test_queries = [
            "What's the weather in New York?",
            "What time is it?",
            "What's my portfolio allocation?",
        ]

        for query in test_queries:
            logger.info(f"\n--- Query: {query}")

            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": query}]}
            )

            for m in result["messages"]:
                for tc in getattr(m, "tool_calls", None) or []:
                    logger.info(f"Tool called: {tc['name']}({tc['args']})")

            logger.info(f"Response: {message_text(result['messages'][-1])}")

        logger.info("\n✓ All tests passed!")
        return True

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    asyncio.run(test_gemini_agent())