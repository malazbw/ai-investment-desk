"""
Agent router/orchestrator - decides which agents to run
"""
from typing import List, Dict, Any
from app.agents.base import BaseAgent
import logging

logger = logging.getLogger(__name__)


class AgentRouter:
    """Routes user messages to appropriate agents"""

    def __init__(self, agents: Dict[str, BaseAgent]):
        """
        Initialize router with available agents

        Args:
            agents: Dict mapping agent names to BaseAgent instances
        """
        self.agents = agents
        self.logger = logger

    def decide_agents(self, user_message: str) -> List[BaseAgent]:
        """
        Determine which agents should handle this message.

        Simple routing logic: always run portfolio agent + smart selection of others.
        Can be enhanced with ML/NLP later.

        Args:
            user_message: User's natural language question

        Returns:
            List of agents to execute
        """
        agents_to_run = []

        # Always include portfolio agent (understands user's holdings)
        if "portfolio" in self.agents:
            agents_to_run.append(self.agents["portfolio"])

        # Keywords for other agents
        keywords_mapping = {
            "market_research": [
                "news", "sentiment", "analyst", "rating", "what's happening",
                "latest", "should i", "outlook", "trend"
            ],
            "macro": [
                "market", "economy", "fed", "interest", "inflation", "vix",
                "conditions", "climate", "macro", "global"
            ],
            "risk": [
                "risk", "lose", "downside", "crash", "volatility", "exposure",
                "danger", "safe", "limit"
            ],
            "valuation": [
                "worth", "price", "valuation", "fair value", "expensive",
                "cheap", "dcf", "multiple", "pe ratio"
            ],
        }

        message_lower = user_message.lower()

        for agent_name, keywords in keywords_mapping.items():
            if agent_name in self.agents:
                if any(keyword in message_lower for keyword in keywords):
                    agents_to_run.append(self.agents[agent_name])

        self.logger.info(
            f"Routing message to agents: {[a.name for a in agents_to_run]}"
        )

        return agents_to_run

    def add_agent(self, name: str, agent: BaseAgent) -> None:
        """Register a new agent"""
        self.agents[name] = agent
        self.logger.info(f"Registered agent: {name}")

    def get_agent(self, name: str) -> BaseAgent:
        """Get agent by name"""
        return self.agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agents"""
        return list(self.agents.keys())
