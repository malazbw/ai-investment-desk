"""
Research Agent internal state for LangGraph workflow
"""
from typing import TypedDict, Any
from app.agents.findings import Finding


class ResearchAgentState(TypedDict, total=False):
    """
    Internal state for Research Agent's agentic loop.

    Flow:
    1. decide_tool_node: LLM analyzes query + tools → decides which tool
    2. execute_tool_node: Execute the selected tool
    3. create_findings_node: Convert tool result to findings with source attribution
    4. assess_node: LLM creates assessment
    """
    # Input
    query: str
    ticker: str

    # Tool decision node output
    tool_decision: dict  # {"tool_name": "get_stock_valuation", "tool_args": {"ticker": "MSFT"}}

    # Tool execution node output
    tool_result: dict  # {"pe_ratio": 27.30, "market_cap": 3.89T, ...}

    # Findings creation node output
    findings: list[dict]  # List of Finding.to_dict()

    # Assessment node output
    assessment: dict  # {"finding": "...", "evidence": [...], "meaning": "...", ...}

    # Metadata
    llm_client: Any
