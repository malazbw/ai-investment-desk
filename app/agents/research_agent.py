import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import yfinance as yf

from app.agents.base import BaseAgent, AgentContext, AgentOutput
from app.agents.findings import Finding, SourceRef, SourceType, EvidenceLevel
from app.agents.assessment import build_assessment


class ResearchAgent(BaseAgent):
    """
    Research Agent answers financial questions about companies.

    Tier 1 (Valuation): P/E ratio, EPS, dividend, market cap, 52-week high/low
    Tier 2 (News): TODO
    Tier 3 (SEC Filings): TODO
    """

    def __init__(self):
        super().__init__(name="research")
        self.logger = logging.getLogger(__name__)

    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Main entry point for Research Agent
        """
        started = time.monotonic()

        try:
            # Step 1: Extract ticker
            ticker = self._extract_ticker(context.user_message)
            if not ticker:
                return self._create_output(
                    False,
                    {},
                    "Could not identify a ticker symbol in your question"
                )

            # Step 2: Classify query type (Tier 1 only for now)
            if not self._is_valuation_query(context.user_message):
                return self._create_output(
                    False,
                    {},
                    "This is not a valuation question. Currently supporting Tier 1 valuation queries only."
                )

            # Step 3: Fetch stock data
            stock_data = self._fetch_stock_data(ticker)
            if "error" in stock_data:
                return self._create_output(
                    False,
                    {},
                    f"Failed to fetch data for {ticker}: {stock_data['error']}"
                )

            # Step 4: Extract relevant metrics based on query
            metrics = self._extract_relevant_metrics(context.user_message, stock_data)

            # Step 5: Create findings with source attribution
            findings = self._create_findings(ticker, metrics, stock_data)

            # Step 6: Create assessment
            assessment = build_assessment(
                finding=f"Found valuation data for {stock_data.get('company_name', ticker)}",
                evidence=[f"{finding['claim']} ({finding['source']['source_name']})" for finding in [f.to_dict() for f in findings]],
                meaning="These metrics show current market valuation",
                counterpoint="Past metrics don't predict future performance",
                confidence="High for current data, moderate for interpretation",
                missing=["Historical comparison", "Analyst consensus", "Forward guidance"]
            )

            # Step 7: Return structured output
            execution_time = (time.monotonic() - started) * 1000

            return self._create_output(
                True,
                {
                    "findings": [f.to_dict() for f in findings],
                    "assessment": assessment,
                    "ticker": ticker,
                    "company_name": stock_data.get("company_name"),
                    "metrics": metrics,
                    "data_source": "Yahoo Finance",
                    "fetched_at": stock_data.get("fetched_at")
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            self.logger.exception("Research Agent failed")
            return self._create_output(
                False,
                {},
                str(e),
                execution_time_ms=(time.monotonic() - started) * 1000
            )

    def _extract_ticker(self, query: str) -> Optional[str]:
        """
        Extract company ticker from user query

        Examples:
        "What is Microsoft's P/E?" → MSFT
        "Apple earnings per share" → AAPL
        "Does Nvidia pay dividend?" → NVDA
        "Tesla 52-week high" → TSLA
        """

        # Mapping of company names to tickers
        company_to_ticker = {
            "microsoft": "MSFT",
            "apple": "AAPL",
            "nvidia": "NVDA",
            "tesla": "TSLA",
            "amazon": "AMZN",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "meta": "META",
            "facebook": "META",
            "netflix": "NFLX",
            "nvidia": "NVDA",
            "intel": "INTC",
            "amd": "AMD",
            "qualcomm": "QCOM",
            "broadcom": "AVGO",
            "oracle": "ORCL",
            "salesforce": "CRM",
            "adobe": "ADBE",
            "cisco": "CSCO",
        }

        query_lower = query.lower()

        # Try company names first
        for company, ticker in company_to_ticker.items():
            if company in query_lower:
                return ticker

        # Try ticker symbols (e.g., "MSFT")
        import re
        match = re.search(r'\b([A-Z]{1,5})\b', query)
        if match:
            return match.group(1)

        return None

    def _is_valuation_query(self, query: str) -> bool:
        """
        Check if query is a Tier 1 valuation question
        """
        valuation_keywords = [
            "p/e", "pe ratio", "market cap", "market value",
            "eps", "earnings per share", "trailing", "forward",
            "dividend", "yield", "52-week", "high", "low",
            "price", "current price", "valuation",
            "earnings", "stock price"
        ]

        query_lower = query.lower()
        return any(kw in query_lower for kw in valuation_keywords)

    def _fetch_stock_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch comprehensive stock data from yfinance

        Returns:
        {
            "ticker": "MSFT",
            "price": 425.30,
            "pe_ratio": 32.5,
            "trailing_eps": 13.08,
            "forward_eps": 15.20,
            "dividend_rate": 2.76,
            "dividend_yield": 0.0065,
            "fifty_two_week_high": 450.00,
            "fifty_two_week_low": 320.00,
            "market_cap": 3100000000000,
            "fetched_at": "2026-11-13T..."
        }
        """

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                "ticker": ticker,
                "price": info.get("currentPrice"),
                "pe_ratio": info.get("trailingPE"),
                "trailing_eps": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),
                "dividend_rate": info.get("dividendRate"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "market_cap": info.get("marketCap"),
                "company_name": info.get("longName", ticker),
                "currency": "USD",
                "fetched_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to fetch data for {ticker}: {e}")
            return {
                "ticker": ticker,
                "error": str(e),
                "fetched_at": datetime.utcnow().isoformat()
            }

    def _extract_relevant_metrics(self, query: str, stock_data: Dict) -> Dict:
        """
        Extract only the metrics the user asked for

        Example:
        Q: "What is Microsoft's P/E ratio?"
        → Extract: pe_ratio only

        Q: "What is Tesla's 52-week high and low?"
        → Extract: fifty_two_week_high, fifty_two_week_low
        """

        query_lower = query.lower()
        metrics = {}

        # P/E Ratio
        if any(kw in query_lower for kw in ["p/e", "pe ratio", "valuation"]):
            metrics["pe_ratio"] = stock_data.get("pe_ratio")

        # Market Cap
        if "market cap" in query_lower or "market value" in query_lower:
            metrics["market_cap"] = stock_data.get("market_cap")

        # Trailing EPS
        if "trailing" in query_lower and "eps" in query_lower:
            metrics["trailing_eps"] = stock_data.get("trailing_eps")

        # Forward EPS
        if "forward" in query_lower and "eps" in query_lower:
            metrics["forward_eps"] = stock_data.get("forward_eps")

        # Dividend
        if "dividend" in query_lower:
            metrics["dividend_rate"] = stock_data.get("dividend_rate")
            metrics["dividend_yield"] = stock_data.get("dividend_yield")

        # 52-Week High/Low
        if "52-week" in query_lower or "high" in query_lower:
            metrics["fifty_two_week_high"] = stock_data.get("fifty_two_week_high")

        if "52-week" in query_lower or "low" in query_lower:
            metrics["fifty_two_week_low"] = stock_data.get("fifty_two_week_low")

        # If nothing specific, return all metrics
        if not metrics:
            metrics = {
                "price": stock_data.get("price"),
                "pe_ratio": stock_data.get("pe_ratio"),
                "trailing_eps": stock_data.get("trailing_eps"),
                "dividend_yield": stock_data.get("dividend_yield"),
                "market_cap": stock_data.get("market_cap")
            }

        return metrics

    def _create_findings(self, ticker: str, metrics: Dict, stock_data: Dict) -> List[Finding]:
        """
        Create structured findings with source attribution
        """

        findings = []

        for metric_name, value in metrics.items():
            if value is None:
                continue

            # Format metric name for display
            metric_display = metric_name.replace("_", " ").title()

            # Create finding
            finding = Finding(
                claim=f"{ticker} {metric_display}: {value}",
                source=SourceRef(
                    source_type=SourceType.PRICE_DATA,
                    source_name="Yahoo Finance",
                    url=f"https://finance.yahoo.com/quote/{ticker}",
                    credibility_score=0.9,
                    fetched_at=datetime.fromisoformat(stock_data.get("fetched_at", datetime.utcnow().isoformat()))
                ),
                evidence_level=EvidenceLevel.PRIMARY,
                confidence_score=0.9,
                timestamp=datetime.utcnow(),
                metadata={
                    "ticker": ticker,
                    "metric": metric_name,
                    "value": str(value),
                    "company_name": stock_data.get("company_name")
                }
            )

            findings.append(finding)

        return findings
