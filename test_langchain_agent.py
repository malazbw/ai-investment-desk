"""
Simple test script to verify LangChain agent pattern works.
Tests with Ollama (free local LLM) or Claude API.
"""
import asyncio
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

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


# ============================================================================
# TEST WITH OLLAMA (FREE LOCAL)
# ============================================================================

async def test_with_ollama():
    """Test agent with local Ollama."""
    logger.info("Testing with Ollama (local)...")

    try:
        from langchain_ollama import OllamaLLM

        # Create LLM
        llm = OllamaLLM(
            base_url="http://localhost:11434",
            model="mistral",
            temperature=0.7,
        )

        # Create tools list
        tools = [get_weather, get_time]

        # Create agent
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt="You are a helpful assistant with access to tools.",
        )

        logger.info("Agent created successfully")

        # Test query
        query = "What's the weather in New York?"
        logger.info(f"Query: {query}")

        result = await agent.ainvoke({"input": query})
        logger.info(f"Result: {result}")

        return True

    except Exception as e:
        logger.error(f"Ollama test failed: {e}", exc_info=True)
        return False


# ============================================================================
# TEST WITH CLAUDE
# ============================================================================

async def test_with_claude():
    """Test agent with Claude API."""
    logger.info("Testing with Claude...")

    try:
        from langchain_anthropic import ChatAnthropic
        import os

        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            logger.warning("CLAUDE_API_KEY not set, skipping Claude test")
            return None

        # Create LLM
        llm = ChatAnthropic(
            model="claude-opus-4-1",
            api_key=api_key,
            temperature=0.7,
        )

        # Create tools list
        tools = [get_weather, get_time]

        # Create agent
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt="You are a helpful assistant with access to tools.",
        )

        logger.info("Agent created successfully")

        # Test query
        query = "What's the weather in San Francisco?"
        logger.info(f"Query: {query}")

        result = await agent.ainvoke({"input": query})
        logger.info(f"Result: {result}")

        return True

    except Exception as e:
        logger.error(f"Claude test failed: {e}", exc_info=True)
        return False


# ============================================================================
# MAIN TEST
# ============================================================================

async def main():
    """Run all tests."""
    logger.info("="*80)
    logger.info("Testing LangChain Agent Pattern")
    logger.info("="*80)

    # Test Ollama (free, local)
    logger.info("\n[1] Testing with Ollama (local, free)...")
    ollama_ok = await test_with_ollama()

    if ollama_ok:
        logger.info("✓ Ollama test PASSED")
    else:
        logger.info("✗ Ollama test FAILED")

    # Test Claude (if API key available)
    logger.info("\n[2] Testing with Claude (requires API key)...")
    claude_ok = await test_with_claude()

    if claude_ok is None:
        logger.info("⊘ Claude test SKIPPED (no API key)")
    elif claude_ok:
        logger.info("✓ Claude test PASSED")
    else:
        logger.info("✗ Claude test FAILED")

    logger.info("\n" + "="*80)
    if ollama_ok or claude_ok:
        logger.info("✓ At least one LLM works - ready to integrate!")
    else:
        logger.info("✗ No LLM tests passed - check configuration")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
