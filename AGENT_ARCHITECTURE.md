# Agent Architecture

This document describes the currently implemented main and portfolio agents. Use it as context when changing, debugging, or extending the agent flow.

## Overview

The application has a two-agent flow for portfolio questions:

```text
User query
    |
    v
Main Investment Assistant (LangChain create_agent / LangGraph)
    |  tool: portfolio_subagent
    v
Portfolio agent (LangChain create_agent / LangGraph)
    |  tool: get_holdings
    v
SQLAlchemy database -> Holding rows and related Asset fields
```

The main agent is the orchestrator. It has one tool, `portfolio_subagent`, which invokes the portfolio agent. The portfolio agent has one tool, `get_holdings`, which reads from the application database. The research agent is not registered as a tool in this main-agent flow.

## Components

### Main agent — `app/agents/main_agent.py`

- `create_main_agent(llm_model)` creates the main LangChain agent.
- Its LangSmith/LangGraph display name is `Main Investment Assistant`.
- It receives one tool: `portfolio_subagent`.
- `run_main_agent(llm_model, user_query)` invokes it with a user message and returns either `{"success": True, "response": ...}` or `{"success": False, "error": ...}`.
- The main agent uses the model passed in as `llm_model`; the module does not select a provider or model itself.

### Portfolio subagent wrapper — `app/agents/main_agent.py`

- `create_portfolio_subagent_tool(llm_model)` creates the portfolio agent, then exposes it to the main agent as a LangChain tool named `portfolio_subagent`.
- The tool accepts a string argument named `query`.
- Its async function invokes the portfolio agent with that query, extracts the final message's text, and returns it to the main agent.
- The tool description is `Answer a question using the user's stored portfolio holdings.`

### Portfolio agent — `app/agents/portfolio_subagent.py`

- `create_portfolio_subagent(llm_model)` creates a LangChain agent using the same injected model as the main agent.
- It has one tool: `get_holdings`.
- Its system prompt says to base answers on information returned by tools.

### Database tool — `get_holdings`

- `get_holdings()` is a read-only LangChain tool in `app/agents/portfolio_subagent.py`.
- It creates a SQLAlchemy session using `get_session_factory()` from `app/database.py`.
- It queries `Holding` rows and returns a list with `symbol`, `quantity`, `current_value`, and `currency`; the symbol and currency are read from each related `Asset`.
- Numeric values are converted to strings before being returned to the LLM.
- The session is closed in a `finally` block.
- This function currently queries all holdings (`session.query(Holding).all()`) and does not accept a user/account ID. Do not assume the current tool scopes data to the authenticated user.

## Typical execution and traces

For a request such as “What are my holdings?”, a successful trace commonly contains four model calls:

1. Main agent model decides to call `portfolio_subagent`.
2. Portfolio agent model decides to call `get_holdings`.
3. Portfolio agent model forms an answer from the database result.
4. Main agent model forms the final user-facing answer from the subagent result.

The exact number of model calls depends on the request and the model's tool decisions. Tool executions (`portfolio_subagent`, `get_holdings`) are not themselves LLM calls. In LangSmith, inspect the parent/child run tree; the root should be named `Main Investment Assistant` for runs created by the current code, and child runs should show the portfolio tool and its internal model/tool steps.

## Testing and tracing references

- `test/agents/test_main_agent.py` is a live Gemini test. It checks that the main agent called `portfolio_subagent`, that the tool returned content, and that the final answer contains the expected holding symbols.
- `app/config.py` contains the optional LangSmith tracing settings. The configured default project name is `ai-investment-desk`.
- The agents receive their LLM as a function argument; tests construct the Gemini model and pass it into `create_main_agent`.

## Guidance for future changes

- Keep database reads in explicit, narrowly scoped tools; do not have the LLM construct SQL.
- Preserve the portfolio tool's structured output and the wrapper's final-text extraction when changing the subagent boundary.
- If adding per-user portfolio access, pass trusted user/account context into the tool and filter the database query. A user-provided query string is not an authorization boundary.
- If a portfolio question should avoid a second LLM decision/answer cycle, consider whether a direct database tool is better than a portfolio agent. That is an architecture decision; it is not how the current flow is wired.
