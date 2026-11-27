"""Live Gemini test for main-agent routing to Tier 1 company research."""
import asyncio
import os

import pytest
from dotenv import load_dotenv

# The repository's local .env may contain a non-boolean DEBUG value.
os.environ["DEBUG"] = "false"
load_dotenv()

google_genai = pytest.importorskip("langchain_google_genai")

from app.agents.main_agent import create_main_agent  # noqa: E402
from app.config import settings  # noqa: E402


QUESTION = (
    "For MSFT, report the available trailing and forward P/E, EPS, market "
    "capitalization, dividend yield, and 52-week high/low. Include the source "
    "and fetch time, and clearly mark any unavailable values."
)


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def test_main_agent_routes_tier1_question_to_research_agent():
    """Invoke the main agent and verify both research tools run for the query."""
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("Set GEMINI_API_KEY in the environment or .env to run this live test")

    model_name = os.getenv("GEMINI_MODEL", settings.gemini_model)
    llm = google_genai.ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        temperature=0.7,
    )
    main_agent = create_main_agent(llm)

    async def invoke_and_collect_tool_events():
        tool_names = []
        final_state = None
        async for event in main_agent.astream_events(
            {"messages": [{"role": "user", "content": QUESTION}]},
            version="v2",
        ):
            if event.get("event") == "on_tool_start":
                tool_names.append(event.get("name"))
            if (
                event.get("event") == "on_chain_end"
                and not event.get("parent_ids")
            ):
                final_state = event.get("data", {}).get("output")
        return tool_names, final_state

    tool_names, final_state = asyncio.run(invoke_and_collect_tool_events())

    assert "research_subagent" in tool_names, (
        f"Main agent did not call research_subagent; observed tool events: {tool_names}"
    )
    assert "get_valuation_metrics" in tool_names, (
        f"Research agent did not call its fundamentals tool; observed: {tool_names}"
    )
    assert isinstance(final_state, dict), "Main agent returned no final state"

    messages = final_state.get("messages", [])
    assert messages, "Main agent returned no messages"
    final_answer = _message_text(messages[-1].content)
    assert final_answer.strip(), "Main agent returned an empty answer"
    assert "MSFT" in final_answer.upper(), "Final answer did not mention MSFT"

    print(f"Agent tools called: {tool_names}")
    print(f"Main agent answer: {final_answer}")
