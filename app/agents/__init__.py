"""
Agent system for AI Investment Desk
"""
from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.router import AgentRouter
from app.agents.execution import execute_agents_parallel
from app.agents.market_research_agent import MarketResearchAgent
from app.agents.macro_agent import MacroContextAgent
from app.agents.risk_manager_agent import RiskManagerAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.valuation_agent import ValuationAgent

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentOutput",
    "AgentRouter",
    "execute_agents_parallel",
    "MarketResearchAgent",
    "MacroContextAgent",
    "RiskManagerAgent",
    "SynthesisAgent",
    "ValuationAgent",
]
