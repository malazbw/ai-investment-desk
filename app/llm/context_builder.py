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
        Handles both structured findings and legacy raw data.

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

            # Check if this agent returned structured findings
            findings = data.get("findings", [])
            assessment = data.get("assessment", {})

            if findings and assessment:
                # Format structured findings with sources
                lines.append(ContextBuilder._format_findings(findings, assessment))
            else:
                # Fall back to legacy formatting
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
    def _format_findings(findings: list, assessment: Dict[str, Any]) -> str:
        """Format structured findings with source citations"""
        lines = []

        # Add main assessment
        if "finding" in assessment:
            lines.append(f"**Finding**: {assessment['finding']}")

        if not findings:
            if "evidence" in assessment:
                lines.append("**Evidence**:")
                for item in assessment["evidence"]:
                    lines.append(f"- {item}")
        else:
            # Group findings by confidence level
            high_confidence = [f for f in findings if f.get("confidence_score", 0) > 0.8]
            medium_confidence = [f for f in findings if 0.5 <= f.get("confidence_score", 0) <= 0.8]
            low_confidence = [f for f in findings if f.get("confidence_score", 0) < 0.5]

            if high_confidence:
                lines.append("**High Confidence (Primary Sources):**")
                for finding in high_confidence:
                    url = finding.get("source", {}).get("url")
                    source_name = finding.get("source", {}).get("source_name", "Unknown")
                    if url:
                        lines.append(f"- {finding['claim']} ([{source_name}]({url}))")
                    else:
                        lines.append(f"- {finding['claim']} ({source_name})")

            if medium_confidence:
                lines.append("**Medium Confidence (Secondary Sources):**")
                for finding in medium_confidence:
                    source_name = finding.get("source", {}).get("source_name", "Unknown")
                    lines.append(f"- {finding['claim']} ({source_name})")

            if low_confidence:
                lines.append("**Lower Confidence:**")
                for finding in low_confidence:
                    source_name = finding.get("source", {}).get("source_name", "Unknown")
                    lines.append(f"- {finding['claim']} ({source_name})")

        # Add assessment fields
        if "meaning" in assessment and assessment["meaning"]:
            lines.append(f"**Meaning**: {assessment['meaning']}")

        if "confidence" in assessment and assessment["confidence"]:
            lines.append(f"**Confidence**: {assessment['confidence']}")

        if "missing" in assessment and assessment["missing"]:
            lines.append(f"**Missing**: {', '.join(assessment['missing'])}")

        if "counterpoint" in assessment and assessment["counterpoint"]:
            lines.append(f"**Counterpoint**: {assessment['counterpoint']}")

        return "\n".join(lines)

    @staticmethod
    def _format_data(data: Dict[str, Any], indent: int = 0) -> str:
        """Recursively format data dict into readable text"""
        lines = []
        indent_str = "  " * indent

        for key, value in data.items():
            # Skip findings and assessment as they're handled separately
            if key in ("findings", "assessment"):
                continue

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
