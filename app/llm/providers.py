"""
LLM abstraction layer - supports multiple providers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

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


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-1"):
        """
        Initialize Claude provider

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.logger = logger

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
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": full_user_message,
                    }
                ],
            )

            response = message.content[0].text
            if message.stop_reason == "max_tokens":
                raise RuntimeError(
                    "Claude response reached the output token limit before completion"
                )
            self.logger.info("Claude response received")
            return response

        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            raise

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
    """Google Gemini Developer API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        api_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ):
        import httpx

        if not api_key:
            raise ValueError("A Gemini API key is required")

        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
        self.logger = logger

    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        context_text = self._format_context(context)
        full_user_message = f"{context_text}\n\nUser Question: {user_message}"

        self.logger.info("Calling Gemini with model %s", self.model)
        try:
            response = await self.client.post(
                f"{self.api_url}/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self.api_key},
                json={
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [
                        {"role": "user", "parts": [{"text": full_user_message}]}
                    ],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topP": 0.9,
                        "topK": 40,
                        "maxOutputTokens": 2048,
                    },
                },
            )
            response.raise_for_status()
            candidates = response.json().get("candidates", [])
            if candidates and candidates[0].get("finishReason") == "MAX_TOKENS":
                raise RuntimeError(
                    "Gemini response reached the output token limit before completion"
                )
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            generated_text = "\n".join(
                part["text"] for part in parts if isinstance(part.get("text"), str)
            ).strip()
            if not generated_text:
                raise ValueError("Gemini returned no text response")

            self.logger.info("Gemini response received")
            return generated_text
        except Exception as e:
            self.logger.error("Gemini API error: %s", e)
            raise

    def _format_context(self, context: Dict[str, Any]) -> str:
        lines = []
        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"\n## {key}")
                lines.extend(f"  {item_key}: {item_value}" for item_key, item_value in value.items())
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
        import httpx

        self.api_url = api_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=300.0)  # Long timeout for inference
        self.logger = logger

    async def analyze(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """Call Ollama API"""
        context_text = self._format_context(context)
        full_user_message = f"{context_text}\n\nUser Question: {user_message}"

        # Build prompt with system instruction
        full_prompt = f"{system_prompt}\n\n{full_user_message}"

        self.logger.info(f"Calling Ollama with model {self.model}")

        try:
            response = await self.client.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "top_k": 40,
                    }
                },
            )

            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.text}")

            result = response.json()
            generated_text = result.get("response", "").strip()

            self.logger.info("Ollama response received")
            return generated_text

        except Exception as e:
            self.logger.error(f"Ollama API error: {e}")
            raise

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
        provider_type: str = "ollama",
        **kwargs
    ) -> LLMProvider:
        """
        Create LLM provider based on type

        Args:
            provider_type: "claude", "gemini", or "ollama"
            **kwargs: Provider-specific arguments

        Returns:
            LLMProvider instance
        """
        if provider_type.lower() == "claude":
            return ClaudeProvider(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "claude-opus-4-1"),
            )
        elif provider_type.lower() == "gemini":
            return GeminiProvider(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "gemini-3.5-flash-lite"),
                api_url=kwargs.get(
                    "api_url", "https://generativelanguage.googleapis.com/v1beta"
                ),
            )
        elif provider_type.lower() == "ollama":
            return OllamaProvider(
                api_url=kwargs.get("api_url", "http://localhost:11434"),
                model=kwargs.get("model", "mistral"),
            )
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
