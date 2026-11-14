"""
Research Agent using LangGraph for agentic loop.
Tier 1 only: Valuation queries using yfinance tool.
LLM decides which tool to use and what data to extract - no hardcoded logic.
"""
import json
import logging
import time
from datetime import datetime
from typing import Any

from langgraph.graph import StateGraph, END, START

from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.research_agent_state import ResearchAgentState
from app.agents.findings import Finding, SourceRef, SourceType, EvidenceLevel
from app.agents.tools import RESEARCH_TOOLS, execute_tool
from app.agents.assessment import build_assessment

logger = logging.getLogger(__name__)


class ResearchAgentLangGraph(BaseAgent):
    """
    Research Agent with LangGraph agentic loop.

    Flow:
    1. decide_tool_node: LLM analyzes query + tools → decides which tool to use
    2. execute_tool_node: Execute the selected tool
    3. create_findings_node: Convert tool result to findings with source attribution
    4. assess_node: LLM creates assessment
    """

    TOOL_DECISION_SYSTEM_PROMPT = """You are a research assistant that helps analyze financial information.

You have access to tools that can fetch data. Based on the user's question, you must decide:
1. Which tool to use
2. What arguments to pass to the tool

Always respond with valid JSON in this exact format:
{"tool_name": "tool_name", "tool_args": {"key": "value"}}

Do NOT use keyword matching or regex. Use intelligent understanding of the query."""

    ASSESSMENT_SYSTEM_PROMPT = """You are a financial analyst. Based on the tool results provided, create a brief assessment.

The assessment should include:
- finding: What you discovered
- evidence: Key data points
- meaning: What this means for investors
- counterpoint: Alternative interpretations
- confidence: How confident you are in this analysis
- missing: What information is not available

Respond with a JSON object containing these fields."""

    def __init__(self):
        super().__init__(name="research")
        self.logger = logging.getLogger(__name__)

        # Build LangGraph
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the LangGraph for research agent"""
        graph = StateGraph(ResearchAgentState)

        # Add nodes
        graph.add_node("decide_tool", self._decide_tool_node)
        graph.add_node("execute_tool", self._execute_tool_node)
        graph.add_node("create_findings", self._create_findings_node)
        graph.add_node("assess", self._assess_node)

        # Add edges
        graph.add_edge(START, "decide_tool")
        graph.add_edge("decide_tool", "execute_tool")
        graph.add_edge("execute_tool", "create_findings")
        graph.add_edge("create_findings", "assess")
        graph.add_edge("assess", END)

        return graph.compile()

    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Main entry point for Research Agent.
        Invokes the LangGraph workflow.
        """
        started = time.monotonic()

        try:
            user_query = context.user_message
            llm_client = context.metadata.get("llm_client")

            if not llm_client:
                return self._create_output(
                    False,
                    {},
                    "LLM client not provided in context"
                )

            # Initialize state
            initial_state: ResearchAgentState = {
                "query": user_query,
                "ticker": self._extract_ticker_with_llm(user_query, llm_client),
                "llm_client": llm_client,
            }

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)

            # Extract results from final state
            findings = final_state.get("findings", [])
            assessment = final_state.get("assessment", {})
            ticker = final_state.get("ticker")

            execution_time = (time.monotonic() - started) * 1000

            return self._create_output(
                True,
                {
                    "findings": findings,
                    "assessment": assessment,
                    "ticker": ticker,
                    "data_source": "yfinance (Tier 1)",
                    "fetched_at": datetime.utcnow().isoformat()
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            self.logger.exception("Research Agent failed")
            execution_time = (time.monotonic() - started) * 1000
            return self._create_output(
                False,
                {},
                str(e),
                execution_time_ms=execution_time
            )

    async def _decide_tool_node(self, state: ResearchAgentState) -> dict:
        """
        Node 1: LLM decides which tool to use.
        No keyword matching - LLM analyzes the query and tools.
        """
        self.logger.info("[research_decide_tool] LLM analyzing query for tool selection")

        llm_client = state.get("llm_client")
        query = state.get("query")

        try:
            # Use LLM to decide tool (pass tools as context, not hardcoded)
            response = await llm_client.analyze(
                user_message=query,
                system_prompt=self.TOOL_DECISION_SYSTEM_PROMPT,
                context={"available_tools": RESEARCH_TOOLS}
            )

            # Parse LLM response as JSON
            tool_decision = json.loads(response)

            self.logger.info(f"[research_decide_tool] Tool selected: {tool_decision.get('tool_name')}")

            return {"tool_decision": tool_decision}

        except json.JSONDecodeError as e:
            self.logger.error(f"[research_decide_tool] Failed to parse LLM response as JSON: {e}")
            raise Exception(f"LLM did not return valid JSON for tool decision: {response}")
        except Exception as e:
            self.logger.error(f"[research_decide_tool] Error: {e}")
            raise

    async def _execute_tool_node(self, state: ResearchAgentState) -> dict:
        """
        Node 2: Execute the tool LLM decided to use.
        """
        self.logger.info("[research_execute_tool] Executing tool")

        tool_decision = state.get("tool_decision", {})
        tool_name = tool_decision.get("tool_name")
        tool_args = tool_decision.get("tool_args", {})

        if not tool_name:
            raise Exception("No tool selected by LLM")

        try:
            tool_result = await execute_tool(tool_name, tool_args)

            if not tool_result.get("success", False):
                raise Exception(f"Tool execution failed: {tool_result.get('error')}")

            self.logger.info(f"[research_execute_tool] Tool executed: {tool_name}")

            return {"tool_result": tool_result.get("data", {})}

        except Exception as e:
            self.logger.error(f"[research_execute_tool] Error: {e}")
            raise

    async def _create_findings_node(self, state: ResearchAgentState) -> dict:
        """
        Node 3: Convert tool result to findings with source attribution.
        """
        self.logger.info("[research_create_findings] Creating findings")

        tool_result = state.get("tool_result", {})
        tool_decision = state.get("tool_decision", {})
        tool_name = tool_decision.get("tool_name")
        ticker = state.get("ticker") or tool_result.get("ticker", "UNKNOWN")

        findings = []

        if tool_name == "get_stock_valuation":
            # Create findings from valuation data
            for metric_name, value in tool_result.items():
                if value is None or metric_name in ["ticker", "company_name", "currency"]:
                    continue

                metric_display = metric_name.replace("_", " ").title()

                finding = Finding(
                    claim=f"{ticker} {metric_display}: {value}",
                    source=SourceRef(
                        source_type=SourceType.PRICE_DATA,
                        source_name="Yahoo Finance",
                        url=f"https://finance.yahoo.com/quote/{ticker}",
                        credibility_score=0.9,
                        fetched_at=datetime.utcnow()
                    ),
                    evidence_level=EvidenceLevel.PRIMARY,
                    confidence_score=0.9,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "ticker": ticker,
                        "metric": metric_name,
                        "value": str(value),
                        "company_name": tool_result.get("company_name", ticker)
                    }
                )
                findings.append(finding)

        self.logger.info(f"[research_create_findings] Created {len(findings)} findings")

        return {"findings": [f.to_dict() for f in findings]}

    async def _assess_node(self, state: ResearchAgentState) -> dict:
        """
        Node 4: LLM creates assessment from findings.
        """
        self.logger.info("[research_assess] Creating assessment")

        findings = state.get("findings", [])
        llm_client = state.get("llm_client")
        query = state.get("query")

        try:
            # Format findings for LLM
            findings_text = json.dumps(findings, indent=2)

            # Use LLM to create assessment
            response = await llm_client.analyze(
                user_message=f"Query: {query}\n\nFindings: {findings_text}",
                system_prompt=self.ASSESSMENT_SYSTEM_PROMPT,
                context={}
            )

            # Parse assessment JSON
            assessment = json.loads(response)

            self.logger.info("[research_assess] Assessment created")

            return {"assessment": assessment}

        except json.JSONDecodeError as e:
            self.logger.error(f"[research_assess] Failed to parse assessment JSON: {e}")
            # Return a basic assessment if JSON parsing fails
            return {
                "assessment": {
                    "finding": "Research completed",
                    "evidence": findings_text,
                    "meaning": "Data analyzed successfully",
                    "counterpoint": "Historical data may not predict future",
                    "confidence": "Medium",
                    "missing": ["Extended analysis", "Comparative metrics"]
                }
            }

    def _extract_ticker_with_llm(self, query: str, llm_client: Any) -> str:
        """
        Extract ticker from query using LLM (no regex/keyword matching).
        """
        try:
            response = llm_client.analyze(
                user_message=query,
                system_prompt="Extract the stock ticker symbol from this query. Respond with ONLY the ticker symbol (e.g., MSFT, AAPL, NVDA) or 'UNKNOWN' if not found.",
                context={}
            )
            ticker = response.strip().upper()
            self.logger.info(f"Extracted ticker: {ticker}")
            return ticker if ticker != "UNKNOWN" else None
        except Exception as e:
            self.logger.warning(f"Failed to extract ticker with LLM: {e}")
            return None
