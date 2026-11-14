"""
LLM abstraction layer - supports multiple providers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import httpx

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """Send message to LLM and get response"""
        pass

    @abstractmethod
    def get_langchain_model(self):
        """Get LangChain-compatible chat model for agents"""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-1"):
        """
        Initialize Claude provider

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        from langchain_anthropic import ChatAnthropic

        self.model = model
        self.logger = logger
        self.llm = ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """Call Claude API"""
        context_text = self._format_context(context)
        full_user_message = f"{context_text}\n\nUser Question: {user_message}"

        self.logger.info(f"Calling Claude with model {self.model}")

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=full_user_message),
            ]
            response = await self.llm.ainvoke(messages)
            result = response.content
            self.logger.info("Claude response received")
            return result

        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            raise

    def get_langchain_model(self):
        """Get LangChain-compatible chat model"""
        return self.llm

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format agent outputs into readable context"""
        lines = []

        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"\n## {key}")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines)


class OllamaProvider(LLMProvider):
    """Local Ollama API provider (free models like Llama, Mistral)"""

    def __init__(self, api_url: str = "http://localhost:11434", model: str = "mistral"):
        """
        Initialize Ollama provider

        Args:
            api_url: Ollama API endpoint (default: localhost)
            model: Model to use (e.g., 'mistral', 'llama2', 'neural-chat')
        """
        from langchain_ollama import OllamaLLM

        self.api_url = api_url.rstrip("/")
        self.model = model
        self.logger = logger
        self.llm = OllamaLLM(
            base_url=self.api_url,
            model=model,
            temperature=0.7,
        )

    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """Call Ollama API"""
        context_text = self._format_context(context)
        full_user_message = f"{context_text}\n\nUser Question: {user_message}"

        self.logger.info(f"Calling Ollama with model {self.model}")

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=full_user_message),
            ]
            response = await self.llm.ainvoke(messages)
            result = response
            self.logger.info("Ollama response received")
            return result

        except Exception as e:
            self.logger.error(f"Ollama API error: {e}")
            raise

    def get_langchain_model(self):
        """Get LangChain-compatible chat model"""
        return self.llm

    async def generate_with_tools(
        self,
        user_message: str,
        system_prompt: str,
        tools: list,
    ) -> Dict[str, Any]:
        """
        Call Ollama to decide which tool to use.

        Returns:
            Dict with tool_name and tool_args
        """
        # Format tools for LLM
        tools_text = self._format_tools(tools)

        full_prompt = f"""{system_prompt}

Available Tools:
{tools_text}

User Query: {user_message}

Respond with a JSON object in this format:
{{"tool_name": "tool_name", "tool_args": {{"arg1": "value1", "arg2": "value2"}}}}
"""

        self.logger.info(f"Calling Ollama for tool decision with model {self.model}")

        try:
            response = await self.client.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temperature for tool selection
                        "top_p": 0.9,
                        "top_k": 40,
                    }
                },
            )

            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.text}")

            result = response.json()
            generated_text = result.get("response", "").strip()

            # Parse JSON response
            import json
            try:
                decision = json.loads(generated_text)
                self.logger.info(f"Tool decision: {decision.get('tool_name')}")
                return decision
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse tool decision JSON: {generated_text}")
                raise Exception(f"Invalid JSON response from Ollama: {generated_text}")

        except Exception as e:
            self.logger.error(f"Ollama tool decision error: {e}")
            raise

    def _format_tools(self, tools: list) -> str:
        """Format tools for LLM presentation"""
        lines = []
        for tool in tools:
            lines.append(f"\nTool: {tool['name']}")
            lines.append(f"Description: {tool['description']}")
            lines.append(f"Parameters: {tool['input_schema']}")
        return "\n".join(lines)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format agent outputs into readable context"""
        lines = []

        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"\n## {key}")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines)


class GeminiProvider(LLMProvider):
    """Google Gemini API provider (free, powerful)"""

    def __init__(self, api_key: str, model: str = "gemini-3.5-flash-lite"):
        """
        Initialize Gemini provider

        Args:
            api_key: Google API key from makersuite.google.com
            model: Gemini model to use
        """
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not api_key:
            raise ValueError("A Gemini API key is required")
        self.api_key = api_key
        self.model = model
        self.logger = logger
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """Call Gemini API"""
        context_text = self._format_context(context)
        full_user_message = f"{context_text}\n\nUser Question: {user_message}"

        self.logger.info(f"Calling Gemini with model {self.model}")

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=full_user_message),
            ]
            response = await self.llm.ainvoke(messages)
            result = response.content
            self.logger.info("Gemini response received")
            return result

        except Exception as e:
            self.logger.error(f"Gemini API error: {e}")
            raise

    def get_langchain_model(self):
        """Get LangChain-compatible chat model"""
        return self.llm

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format agent outputs into readable context"""
        lines = []

        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"\n## {key}")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines)


class LLMFactory:
    """Factory for creating LLM providers"""

    @staticmethod
    def create_provider(
        provider_type: str = "gemini",
        **kwargs
    ) -> LLMProvider:
        """
        Create LLM provider based on type

        Args:
            provider_type: "gemini", "claude" or "ollama"
            **kwargs: Provider-specific arguments

        Returns:
            LLMProvider instance
        """
        if provider_type.lower() == "claude":
            return ClaudeProvider(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "claude-opus-4-1"),
            )
        elif provider_type.lower() == "ollama":
            return OllamaProvider(
                api_url=kwargs.get("api_url", "http://localhost:11434"),
                model=kwargs.get("model", "mistral"),
            )
        elif provider_type.lower() == "gemini":
            return GeminiProvider(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "gemini-3.5-flash-lite"),
            )
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
