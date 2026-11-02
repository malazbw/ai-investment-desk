"""
Context builder - aggregates and formats agent outputs for Claude
"""
from typing import List, Dict, Any
from app.agents.base import AgentOutput
import logging

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds context from agent outputs for Claude consumption"""

    @staticmethod
    def build_context(agent_outputs: List[AgentOutput]) -> Dict[str, Any]:
        """
        Aggregate agent outputs into context for Claude.

        Args:
            agent_outputs: List of AgentOutput from executed agents

        Returns:
            Dict with formatted context for Claude
        """
        context = {}
        errors = []

        for output in agent_outputs:
            if output.success:
                context[output.agent_name] = output.data
            else:
                errors.append(f"{output.agent_name}: {output.error}")
                # Still include data even if there was an error
                context[output.agent_name] = output.data

        if errors:
            context["_errors"] = errors
            logger.warning(f"Some agents reported errors: {errors}")

        return context

    @staticmethod
    def format_for_prompt(context: Dict[str, Any]) -> str:
        """
        Format context dict into readable text for Claude prompt.

        Args:
            context: Aggregated context from agents

        Returns:
            Formatted text for inclusion in Claude prompt
        """
        lines = ["# Portfolio Analysis Context\n"]

        for agent_name, data in context.items():
            if agent_name.startswith("_"):
                # Skip internal fields for prompt
                continue

            lines.append(f"## {ContextBuilder._format_agent_name(agent_name)}")
            lines.append(ContextBuilder._format_data(data))
            lines.append("")

        if "_errors" in context:
            lines.append("## Warnings")
            for error in context["_errors"]:
                lines.append(f"- {error}")

        return "\n".join(lines)

    @staticmethod
    def _format_agent_name(name: str) -> str:
        """Format agent name for display"""
        # Convert snake_case to Title Case
        return " ".join(word.capitalize() for word in name.split("_"))

    @staticmethod
    def _format_data(data: Dict[str, Any], indent: int = 0) -> str:
        """Recursively format data dict into readable text"""
        lines = []
        indent_str = "  " * indent

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}**{key}:**")
                lines.append(ContextBuilder._format_data(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{indent_str}**{key}:**")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(ContextBuilder._format_data(item, indent + 1))
                    else:
                        lines.append(f"{indent_str}  - {item}")
            else:
                # Format key name
                key_display = " ".join(word.capitalize() for word in key.split("_"))
                lines.append(f"{indent_str}- {key_display}: {value}")

        return "\n".join(lines)
