"""
Agent system for AI Investment Desk

Following LangChain subagents pattern:
- main_agent.py: Orchestrator that routes to subagents
- portfolio_subagent.py: Handles portfolio queries
- research_subagent.py: Handles valuation research (Tier 1+)
- findings.py: Source-attributed findings dataclasses
"""

__all__ = [
    "main_agent",
    "portfolio_subagent",
    "research_subagent",
    "findings",
]
