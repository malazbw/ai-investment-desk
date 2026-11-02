"""
LLM client wrapper - abstracted to support multiple providers
"""
from typing import Dict, Any
import logging
from app.llm.providers import LLMProvider

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client supporting multiple providers"""

    def __init__(self, provider: LLMProvider):
        """
        Initialize with an LLM provider

        Args:
            provider: LLMProvider instance (Claude, Ollama, etc)
        """
        self.provider = provider
        self.logger = logger

    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Send message to LLM with context and get response.

        Args:
            user_message: User's natural language question
            system_prompt: System prompt defining agent behavior
            context: Structured data from agents (holdings, news, etc)

        Returns:
            LLM's analysis/response
        """
        self.logger.info(f"Analyzing with provider: {self.provider.__class__.__name__}")

        try:
            response = await self.provider.analyze(
                user_message=user_message,
                system_prompt=system_prompt,
                context=context,
            )
            return response

        except Exception as e:
            self.logger.error(f"LLM analysis error: {e}")
            raise


# For backwards compatibility
ClaudeClient = LLMClient
