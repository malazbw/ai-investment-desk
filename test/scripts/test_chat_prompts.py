import asyncio
import json
from types import SimpleNamespace

from app.agents import main_agent
from scripts import test_chat_prompts


def test_trace_shows_tool_inputs_outputs_and_plain_text_response(monkeypatch, capsys):
    class FakeAgent:
        async def astream_events(self, input, version):
            assert input == {"messages": [{"role": "user", "content": "find news"}]}
            assert version == "v2"
            yield {
                "event": "on_tool_start",
                "name": "get_company_news",
                "data": {"input": {"ticker": "MSFT"}},
            }
            yield {
                "event": "on_tool_end",
                "name": "get_company_news",
                "data": {"output": '{"status":"ok"}'},
            }
            yield {
                "event": "on_chain_end",
                "parent_ids": [],
                "data": {
                    "output": {
                        "messages": [
                            SimpleNamespace(
                                content=[{"type": "text", "text": "Found news."}]
                            )
                        ]
                    }
                },
            }

    monkeypatch.setattr(main_agent, "create_main_agent", lambda model: FakeAgent())

    result = asyncio.run(
        test_chat_prompts.invoke_prompt(object(), "find news", trace=True)
    )
    output = capsys.readouterr().out

    assert result == {"success": True, "response": "Found news."}
    assert "[tool start] get_company_news" in output
    assert '"ticker": "MSFT"' in output
    assert '[tool end] get_company_news' in output
    assert '{"status":"ok"}' in output


def test_news_trace_summarizes_articles_without_snippets():
    output = test_chat_prompts.format_tool_output(
        json.dumps(
            {
                "status": "ok",
                "ticker": "NVDA",
                "source": "NewsAPI",
                "articles": [
                    {
                        "headline": "Nvidia reports quarterly results",
                        "publisher": "Example News",
                        "published_at": "2026-11-27T12:00:00+00:00",
                        "url": "https://example.com/nvidia",
                        "snippet": "Long article content should not be printed.",
                    }
                ],
            }
        )
    )

    assert "1 article(s)" in output
    assert "Nvidia reports quarterly results" in output
    assert "https://example.com/nvidia" in output
    assert "Long article content should not be printed" not in output
