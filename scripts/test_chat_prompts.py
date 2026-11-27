#!/usr/bin/env python3
"""Run prompts through the same main-agent path used by the chat API."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_PROMPTS = (
    "What are my current portfolio holdings?",
    "For Microsoft (MSFT), report the available valuation metrics.",
    (
        "Find recent NewsAPI headlines about Microsoft (MSFT). "
        "Include the publisher, publication date, and URL."
    ),
    "Explain the difference between trailing and forward P/E ratios.",
)


def get_llm_model() -> Any:
    from app.config import settings

    settings.debug = False
    from app.routes import llm_client

    if llm_client is None:
        raise RuntimeError(
            "The configured LLM provider could not be initialized. "
            "Check LLM_PROVIDER and its credentials in .env."
        )
    return llm_client.provider.get_langchain_model()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send test prompts through the configured chatbot main agent."
    )
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help="Prompt to run. Repeat this option to run multiple prompts.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enter prompts interactively instead of running the default suite.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print tool calls and results locally while each prompt runs.",
    )
    return parser.parse_args()


def format_trace_value(value: Any, limit: int = 1200) -> str:
    content = getattr(value, "content", None)
    if content is not None:
        value = content
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    if len(text) > limit:
        return f"{text[:limit]} ... [truncated]"
    return text


def format_tool_output(value: Any) -> str:
    content = getattr(value, "content", None)
    if content is not None:
        value = content
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("articles"), list):
            articles = payload["articles"]
            lines = [
                (
                    f"{payload.get('status', 'unknown')} news for "
                    f"{payload.get('ticker', 'unknown ticker')}: "
                    f"{len(articles)} article(s), source {payload.get('source', 'unknown')}."
                )
            ]
            for article in articles[:5]:
                lines.append(
                    "- "
                    f"{article.get('headline', 'Untitled')} | "
                    f"{article.get('publisher', 'Unknown publisher')} | "
                    f"{article.get('published_at', 'Unknown date')}"
                )
                if article.get("url"):
                    lines.append(f"  {article['url']}")
            if len(articles) > 5:
                lines.append(f"... and {len(articles) - 5} more article(s)")
            return format_trace_value("\n".join(lines))
    return format_trace_value(value)


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


async def invoke_prompt(
    llm_model: Any, prompt: str, trace: bool = False
) -> dict[str, Any]:
    if not trace:
        from app.agents.main_agent import run_main_agent

        return await run_main_agent(llm_model, prompt)

    from app.agents.main_agent import create_main_agent

    agent = create_main_agent(llm_model)
    final_state = None
    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": prompt}]},
        version="v2",
    ):
        event_name = event.get("event")
        if event_name == "on_tool_start":
            print(f"\n  [tool start] {event.get('name')}")
            print(f"  input: {format_trace_value(event.get('data', {}).get('input'))}")
        elif event_name == "on_tool_end":
            print(f"  [tool end] {event.get('name')}")
            if event.get("name") not in {"research_subagent", "portfolio_subagent"}:
                print(
                    "  output: "
                    f"{format_tool_output(event.get('data', {}).get('output'))}"
                )
        elif event_name == "on_tool_error":
            print(f"  [tool error] {event.get('name')}: {event.get('data', {})}")
        elif event_name == "on_chain_end" and not event.get("parent_ids"):
            final_state = event.get("data", {}).get("output")

    messages = final_state.get("messages", []) if isinstance(final_state, dict) else []
    if not messages:
        return {"success": False, "error": "The agent returned no messages."}

    response = content_text(getattr(messages[-1], "content", messages[-1]))
    return {"success": bool(response.strip()), "response": response}


async def run_prompts(prompts: Sequence[str], trace: bool = False) -> int:

    llm_model = get_llm_model()
    failures = 0

    for index, prompt in enumerate(prompts, start=1):
        print(f"\n[{index}/{len(prompts)}] Prompt: {prompt}")
        result = await invoke_prompt(llm_model, prompt, trace)
        if result.get("success"):
            print(f"Response:\n{result['response']}")
        else:
            failures += 1
            print(f"Agent error: {result.get('error', 'Unknown error')}")

    print(f"\nCompleted {len(prompts)} prompt(s); {failures} failed.")
    return 1 if failures else 0


async def run_interactive(trace: bool = False) -> int:
    llm_model = get_llm_model()
    print("Enter prompts (blank line or Ctrl-D to exit).")
    while True:
        try:
            prompt = input("\nYou: ").strip()
        except EOFError:
            print()
            return 0
        if not prompt:
            return 0

        result = await invoke_prompt(llm_model, prompt, trace)
        if result.get("success"):
            print(f"Assistant: {result['response']}")
        else:
            print(f"Agent error: {result.get('error', 'Unknown error')}")


def main() -> int:
    args = parse_args()
    try:
        if args.interactive:
            if args.prompts:
                raise ValueError("--interactive cannot be combined with --prompt.")
            return asyncio.run(run_interactive(trace=args.trace))

        prompts = args.prompts or DEFAULT_PROMPTS
        return asyncio.run(run_prompts(prompts, trace=args.trace))
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
