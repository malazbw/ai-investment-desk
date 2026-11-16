"""Live Gemini integration test for the database-backed portfolio agent."""
import asyncio
import json
import os

import pytest
from dotenv import load_dotenv

# The repository's local .env may contain a non-boolean DEBUG value.
os.environ["DEBUG"] = "false"
load_dotenv()

google_genai = pytest.importorskip("langchain_google_genai")

from app.agents.portfolio_subagent import (  # noqa: E402
    create_portfolio_subagent,
    get_holdings,
)
from app.config import settings  # noqa: E402


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


def test_portfolio_agent_calls_holdings_tool_and_answers():
    """Invoke the portfolio agent and compare the tool result with the DB."""
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("Set GEMINI_API_KEY in the environment or .env to run this live test")

    model_name = os.getenv("GEMINI_MODEL", settings.gemini_model)
    llm = google_genai.ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        temperature=0.7,
    )
    agent = create_portfolio_subagent(llm)

    expected_holdings = get_holdings.invoke({})
    result = asyncio.run(
        agent.ainvoke({
            "messages": [{"role": "user", "content": "What's my holdings?"}]
        })
    )

    messages = result.get("messages", [])
    tool_calls = [
        call
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
    ]
    assert any(call["name"] == "get_holdings" for call in tool_calls)

    tool_messages = [message for message in messages if getattr(message, "type", "") == "tool"]
    assert tool_messages, "Agent called the holdings tool but returned no tool result"
    actual_holdings = json.loads(tool_messages[-1].content)
    assert actual_holdings == expected_holdings

    answer = _message_text(messages[-1].content)
    assert answer.strip(), "Agent returned an empty final answer"
    print(f"Agent answer: {answer}")
