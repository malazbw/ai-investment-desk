"""
Base agent class and interfaces
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context passed to agents"""
    user_message: str
    portfolio_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    """Output from agent execution"""
    agent_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Execute agent logic and return output.

        Args:
            context: AgentContext with user message and portfolio data

        Returns:
            AgentOutput with results
        """
        pass

    def _create_output(
        self,
        success: bool,
        data: Dict[str, Any],
        error: Optional[str] = None,
        execution_time_ms: float = 0.0,
    ) -> AgentOutput:
        """Helper to create AgentOutput"""
        return AgentOutput(
            agent_name=self.name,
            success=success,
            data=data,
            error=error,
            execution_time_ms=execution_time_ms,
        )
