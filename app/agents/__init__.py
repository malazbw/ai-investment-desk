"""
Agent system for AI Investment Desk
"""
from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.router import AgentRouter
from app.agents.execution import execute_agents_parallel

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentOutput",
    "AgentRouter",
    "execute_agents_parallel",
]
