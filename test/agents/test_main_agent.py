"""Live Gemini test for main-agent routing to the portfolio subagent."""
import asyncio
import os

import pytest
from dotenv import load_dotenv

# The repository's local .env may contain a non-boolean DEBUG value.
os.environ["DEBUG"] = "false"
load_dotenv()

google_genai = pytest.importorskip("langchain_google_genai")

from app.agents.main_agent import create_main_agent  # noqa: E402
from app.agents.portfolio_subagent import get_holdings  # noqa: E402
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


def test_main_agent_calls_portfolio_agent_for_holdings():
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
    expected_holdings = get_holdings.invoke({})

    result = asyncio.run(
        main_agent.ainvoke({
            "messages": [{"role": "user", "content": "What are my holdings?"}]
        })
    )

    messages = result.get("messages", [])
    tool_calls = [
        call
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
    ]
    assert any(call["name"] == "portfolio_subagent" for call in tool_calls), (
        "Main agent did not call the portfolio subagent"
    )

    tool_results = [
        _message_text(message.content)
        for message in messages
        if getattr(message, "type", "") == "tool"
    ]
    assert tool_results, "Portfolio subagent returned no result"
    final_answer = _message_text(messages[-1].content)
    assert final_answer.strip(), "Main agent returned an empty answer"

    for holding in expected_holdings:
        assert holding["symbol"] in " ".join(tool_results)
        assert holding["symbol"] in final_answer

    print(f"Main agent called: {[call['name'] for call in tool_calls]}")
    print(f"Main agent answer: {final_answer}")
