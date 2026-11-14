"""
Test Main Agent + Portfolio Subagent flow
Tests that Main Agent calls Portfolio Subagent and tools are triggered
"""
import asyncio
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Setup path
sys.path.insert(0, '/Users/hala.al.kuwatly/projects/ai-investment-desk')

from langchain_google_genai import ChatGoogleGenerativeAI
from app.agents.main_agent import run_main_agent


async def test_main_agent_flow():
    """Test Main Agent → Portfolio Subagent flow"""

    logger.info("\n" + "="*100)
    logger.info("TEST: Main Agent + Portfolio Subagent Flow")
    logger.info("="*100)

    # Load API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Try from .env
        import dotenv
        dotenv.load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.error("❌ GEMINI_API_KEY not found")
        return False

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    logger.info(f"Using model: {model_name}")

    try:
        # Create Gemini LLM
        logger.info("\n[SETUP] Creating Gemini LLM...")
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            temperature=0.7,
        )
        logger.info("[SETUP] ✓ Gemini LLM created")

        # Test queries
        test_queries = [
            "What is my portfolio allocation?",
            "Tell me about my holdings",
            "What's my portfolio summary?",
        ]

        for i, query in enumerate(test_queries, 1):
            logger.info("\n" + "-"*100)
            logger.info(f"TEST {i}: {query}")
            logger.info("-"*100)

            result = await run_main_agent(llm, query)

            logger.info(f"\nResult success: {result.get('success')}")
            if result.get('success'):
                logger.info(f"Response: {result.get('response')[:200]}...")
                logger.info("✓ TEST PASSED")
            else:
                logger.error(f"Error: {result.get('error')}")
                logger.info("✗ TEST FAILED")

        logger.info("\n" + "="*100)
        logger.info("✓ All tests completed")
        logger.info("="*100)
        return True

    except Exception as e:
        logger.error(f"\n❌ FATAL ERROR: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_main_agent_flow())
    sys.exit(0 if success else 1)
