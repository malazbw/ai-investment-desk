"""
Agent router/orchestrator - decides which agents to run
"""
from typing import List, Dict, Optional
from app.agents.base import BaseAgent
from app.agents.tools import extract_company_symbols
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

        # Broad investment-action questions benefit from all available perspectives.
        message_lower = user_message.lower()
        broad_analysis_keywords = (
            "should i",
            "what do you think",
            "analyze",
            "analyse",
            "recommend",
            "buy",
            "sell",
            "hold",
            "invest in",
        )
        include_all_specialists = any(
            keyword in message_lower for keyword in broad_analysis_keywords
        )
        has_company_target = bool(extract_company_symbols(user_message))

        keywords_mapping = {
            "market_research": [
                "news", "sentiment", "analyst", "rating", "what's happening",
                "latest", "outlook", "trend",
            ],
            "macro": [
                "economy", "fed", "interest", "inflation", "vix",
                "conditions", "macro", "global",
            ],
            "risk": [
                "risk", "lose", "downside", "crash", "volatility", "exposure",
                "danger", "safe", "limit", "concentration",
            ],
            "valuation": [
                "worth", "price", "valuation", "fair value", "expensive",
                "cheap", "dcf", "multiple", "pe ratio", "p/e",
                "fundamental",
            ],
        }

        for agent_name, keywords in keywords_mapping.items():
            if agent_name not in self.agents:
                continue
            if include_all_specialists or any(
                keyword in message_lower for keyword in keywords
            ) or (agent_name == "market_research" and has_company_target):
                agents_to_run.append(self.agents[agent_name])

        self.logger.info(
            f"Routing message to agents: {[a.name for a in agents_to_run]}"
        )

        return agents_to_run

    def add_agent(self, name: str, agent: BaseAgent) -> None:
        """Register a new agent"""
        self.agents[name] = agent
        self.logger.info(f"Registered agent: {name}")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name"""
        return self.agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agents"""
        return list(self.agents.keys())
