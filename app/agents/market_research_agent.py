"""Portfolio market-research agent backed by stored company news."""

import re
import time
from datetime import datetime
from typing import Any, Dict

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.assessment import build_assessment
from app.agents.tools import CompanyResearchTool, extract_company_symbols
from app.services import NewsService

COMPANY_TERMS = {
    "AAPL": ("apple", "iphone", "app store", "apple pay"),
    "MSFT": ("microsoft", "azure", "windows", "xbox", "microsoft copilot"),
}
TOPIC_TERMS = {
    "earnings_and_results": (
        "earnings", "revenue", "profit", "quarterly results", "financial results",
        "eps", "guidance", "beat", "miss",
    ),
    "products_and_demand": (
        "iphone", "product", "launch", "consumer", "demand", "sales",
        "app store", "apple pay", "windows", "xbox",
    ),
    "cash_flow_and_capital_returns": (
        "free cash", "cash flow", "dividend", "buyback", "capital return",
    ),
    "ai_and_investment": (
        "ai", "artificial intelligence", "capex", "capital expenditure",
        "infrastructure", "cloud", "data center",
    ),
    "valuation_and_analyst_views": (
        "valuation", "valuations", "analyst", "price target", "buy", "hold",
        "bearish", "bullish", "overvalued", "undervalued",
    ),
    "regulation_and_filings": (
        "sec filing", "8-k", "10-k", "10-q", "antitrust", "regulation",
        "lawsuit", "investigation",
    ),
}
POSITIVE_TERMS = (
    "beat", "growth", "record", "working", "robust", "strong", "buy",
    "undervalued", "upgrade", "bought",
)
NEGATIVE_TERMS = (
    "miss", "drop", "fall", "bearish", "risk", "concern", "downgrade",
    "lawsuit", "investigation", "overvalued",
)
NEWS_ANALYST_PROMPT = """You are the market-research specialist for an investment analysis desk.
Analyze only the supplied SEC facts, price metadata, financial trend calculations, and news.

Rules:
- Full article bodies have not been fetched. A publisher-provided summary snippet, when
  present, is not a substitute for the article or independent verification.
- Cite each item using its exact symbol, headline, publisher, and publication date.
- Structure analysis as: business/fundamental evidence; growth and profitability; valuation;
  news and competitive evidence; risks/counterpoints; confidence and missing evidence.
- Use only supplied financial facts and dates. Distinguish reported results from derived arithmetic
  and interpretation. Do not invent business drivers, competitors, market share, forecasts, or
  catalysts that are absent from the evidence.
- Interpret P/E as a price-to-historical-earnings multiple, not a cheap/expensive verdict. A
  relative valuation conclusion requires actual comparable peer or historical data.
- Treat headlines/snippets as unverified claims and cite them; don't state a headline's claim as fact.
- Explain only plausible relevance to the named company; do not make buy/sell/hold recommendations.
- State clearly when the evidence is insufficient to support a thesis.
- Keep the response under 350 words. Use compact sections and avoid repeating raw data."""


class MarketResearchAgent(BaseAgent):
    """Analyze stored portfolio news and research explicitly requested tickers."""

    def __init__(
        self, company_research_tool: CompanyResearchTool | None = None
    ) -> None:
        super().__init__(name="market_research")
        self.company_research_tool = company_research_tool or CompanyResearchTool()

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        if term in {"ai", "eps", "buy", "hold"}:
            return re.search(rf"\b{re.escape(term)}\b", text) is not None
        return term in text

    @classmethod
    def _analyze_headline(
        cls, symbol: str, headline: str, description: str = ""
    ) -> Dict[str, Any]:
        normalized = f"{headline} {description or ''}".casefold()
        terms = COMPANY_TERMS.get(symbol.upper(), (symbol.casefold(),))
        company_match = any(cls._contains_term(normalized, term) for term in terms)
        ticker_match = re.search(
            rf"(?<![A-Z0-9]){re.escape(symbol.upper())}(?![A-Z0-9])",
            headline.upper(),
        ) is not None
        topics = [
            topic
            for topic, keywords in TOPIC_TERMS.items()
            if any(cls._contains_term(normalized, keyword) for keyword in keywords)
        ]
        if not (company_match or ticker_match) or not topics:
            return {
                "relevant": False,
                "reason": "No company-specific investment topic found in headline.",
            }

        positive = any(cls._contains_term(normalized, term) for term in POSITIVE_TERMS)
        negative = any(cls._contains_term(normalized, term) for term in NEGATIVE_TERMS)
        if "?" in headline:
            tone = "not_clear_from_headline"
        elif positive and negative:
            tone = "mixed"
        elif positive:
            tone = "positive_wording"
        elif negative:
            tone = "negative_wording"
        else:
            tone = "not_clear_from_headline"

        return {
            "relevant": True,
            "topics": topics,
            "tone": tone,
            "analysis": (
                "The supplied headline/snippet wording is favorable; verify the article and underlying figures."
                if tone == "positive_wording"
                else "The supplied headline/snippet wording flags a potential concern; verify the article and evidence."
                if tone == "negative_wording"
                else "The supplied headline/snippet does not establish a clear positive or negative effect."
            ),
            "evidence_level": (
                "headline_and_publisher_snippet"
                if description
                else "headline_only"
            ),
        }

    async def execute(self, context: AgentContext) -> AgentOutput:
        started = time.monotonic()
        db = context.metadata.get("db")
        if db is None:
            return self._create_output(
                False, {}, "Database session not provided in agent context"
            )

        try:
            articles_by_symbol = NewsService.get_portfolio_news(db, days=30, limit=10)
            held_symbols = set(articles_by_symbol)
            requested_symbols = extract_company_symbols(context.user_message)
            external_symbols = [
                symbol for symbol in requested_symbols if symbol not in held_symbols
            ]
            on_demand_research = []
            for symbol in external_symbols:
                try:
                    on_demand_research.append(
                        await self.company_research_tool.research(symbol)
                    )
                except (RuntimeError, ValueError) as exc:
                    self.logger.warning(
                        "On-demand company research failed for %s: %s",
                        symbol,
                        exc,
                    )
                    on_demand_research.append(
                        {
                            "symbol": symbol,
                            "status": "error",
                            "reason": str(exc),
                        }
                    )

            stored_articles = [
                {"symbol": symbol, **article}
                for symbol, symbol_articles in articles_by_symbol.items()
                for article in symbol_articles
            ]
            stored_articles.sort(
                key=lambda article: datetime.fromisoformat(
                    article["published_date"].replace("Z", "+00:00")
                ).timestamp(),
                reverse=True,
            )
            articles = []
            for article in stored_articles:
                assessment = self._analyze_headline(
                    article["symbol"],
                    article["headline"],
                    article.get("description") or "",
                )
                if assessment["relevant"]:
                    articles.append({**article, **assessment})

            findings_by_symbol = {}
            for article in articles:
                finding = findings_by_symbol.setdefault(
                    article["symbol"],
                    {"relevant_article_count": 0, "topics": set(), "articles": []},
                )
                finding["relevant_article_count"] += 1
                finding["topics"].update(article["topics"])
                finding["articles"].append(
                    {
                        "headline": article["headline"],
                        "description": article.get("description"),
                        "source": article["source"],
                        "published_date": article["published_date"],
                        "url": article["url"],
                        "topics": article["topics"],
                        "tone": article["tone"],
                        "analysis": article["analysis"],
                        "evidence_level": article["evidence_level"],
                    }
                )
            findings = {
                symbol: {
                    **value,
                    "topics": sorted(value["topics"]),
                    "summary": (
                        "Stored headlines mention "
                        + ", ".join(topic.replace("_", " ") for topic in sorted(value["topics"]))
                        + ". Full article text was not fetched, so material impact cannot be confirmed."
                    ),
                }
                for symbol, value in findings_by_symbol.items()
            }
            llm_analysis = None
            llm_analysis_status = "not_configured"
            analysis_warnings = []
            llm_client = context.metadata.get("llm_client")
            if (articles or on_demand_research) and llm_client is not None:
                try:
                    on_demand_summary = []
                    for company in on_demand_research:
                        sources = company.get("sources", {})
                        sec = sources.get("sec", {})
                        price = sources.get("market_price", {})
                        news = sources.get("news", {})
                        valuation = company.get("valuation", {})
                        on_demand_summary.append(
                            {
                                "symbol": company.get("symbol"),
                                "company_name": company.get("company_name"),
                                "source_statuses": {
                                    source: details.get("status")
                                    for source, details in sources.items()
                                },
                                "price": {
                                    key: price.get(key)
                                    for key in ("price", "currency", "date", "source")
                                },
                                "valuation": {
                                    key: valuation.get(key)
                                    for key in (
                                        "pe_ratio",
                                        "net_profit_margin_percent",
                                        "free_cash_flow",
                                    )
                                },
                                "year_over_year_growth": valuation.get(
                                    "year_over_year_growth", {}
                                ),
                                "fundamental_findings": company.get(
                                    "fundamental_analysis", {}
                                ).get("findings", []),
                                "valuation_interpretation": company.get(
                                    "fundamental_analysis", {}
                                ).get("valuation_interpretation"),
                                "news_evidence_level": news.get("evidence_level"),
                                "news_articles": news.get("articles", [])[:5],
                            }
                        )
                    llm_analysis = await llm_client.analyze(
                        user_message=(
                            "Give an evidence-led assessment of each explicitly researched "
                            "company. Explain what the supplied fundamentals, calculated "
                            "trends, valuation inputs, and news do and do not support. "
                            "Give the strongest evidence-supported positive case and "
                            "the main counterargument. Do not give an investment recommendation. "
                            "Keep the complete response under 300 words."
                        ),
                        system_prompt=NEWS_ANALYST_PROMPT,
                        context={
                            "stored_portfolio_news": findings,
                            "on_demand_company_research": on_demand_summary,
                        },
                    )
                    llm_analysis_status = "available"
                except Exception as exc:
                    llm_analysis_status = "failed"
                    analysis_warnings.append(
                        f"LLM news analysis failed: {exc}"
                    )
                    self.logger.exception("LLM news analysis failed")
            elif articles or on_demand_research:
                analysis_warnings.append(
                    "No LLM client was supplied; only deterministic source and metric analysis is available."
                )
            snippet_count = sum(
                bool(article.get("description")) for article in articles
            )
            companies = sorted(findings)
            assessment_finding = (
                f"Found {len(articles)} relevant stored items across "
                f"{len(companies)} portfolio companies."
                if articles
                else "No relevant stored company-news items were found."
            )
            assessment_evidence = [
                f"{len(articles)} items passed company/topic filtering; "
                f"{snippet_count} include a publisher-provided summary snippet."
            ]
            for symbol, finding in findings.items():
                assessment_evidence.append(
                    f"{symbol}: {finding['relevant_article_count']} items on "
                    + ", ".join(finding["topics"])
                    + "."
                )
            for company in on_demand_research:
                if company.get("status") == "error":
                    assessment_evidence.append(
                        f"{company['symbol']} on-demand research failed: "
                        f"{company['reason']}"
                    )
                    continue
                valuation = company.get("valuation", {})
                assessment_evidence.append(
                    f"{company['symbol']} on-demand source status: "
                    + ", ".join(
                        f"{source}={details.get('status')}"
                        for source, details in company.get("sources", {}).items()
                    )
                    + (
                        f"; P/E={valuation['pe_ratio']}."
                        if valuation.get("pe_ratio") is not None
                        else "; P/E unavailable from current on-demand sources."
                    )
                )
            if on_demand_research:
                assessment_finding += (
                    f" On-demand research was requested for "
                    f"{', '.join(external_symbols)}."
                )
            return self._create_output(
                True,
                {
                    "status": "available" if articles else "no_recent_news",
                    "lookback_days": 30,
                    "article_count": len(articles),
                    "stored_article_count": len(stored_articles),
                    "excluded_article_count": len(stored_articles) - len(articles),
                    "articles": articles,
                    "findings_by_symbol": findings,
                    "on_demand_research": on_demand_research,
                    "on_demand_analysis": (
                        llm_analysis if on_demand_research else None
                    ),
                    "assessment": build_assessment(
                        finding=assessment_finding,
                        evidence=assessment_evidence,
                        meaning=(
                            "These items can identify topics worth checking, but "
                            "headlines and publisher snippets alone do not establish "
                            "a company's results or the likely effect on its share price. "
                            "On-demand research is kept separate from stored portfolio holdings."
                        ),
                        counterpoint=(
                            "Headlines may be incomplete, opinionated, duplicated, "
                            "or contradicted by the full article and primary filings."
                        ),
                        confidence=(
                            "Low for claims or investment impact; moderate only for "
                            "the presence and wording of the stored headlines/snippets."
                        ),
                        missing=[
                            "Full article text and independent verification of claims.",
                            "Primary filing or earnings data that supports the claims.",
                            "A wider source set and event impact analysis.",
                            "Unavailable on-demand sources listed for explicitly requested companies.",
                        ],
                    ),
                    "llm_analysis_status": llm_analysis_status,
                    "llm_analysis": llm_analysis,
                    "analysis_warnings": analysis_warnings,
                    "analysis_method": (
                        "Company-specific headline filtering, cautious headline wording "
                        "classification, SEC-reported annual facts and derived trends, "
                        "on-demand market prices and publisher news summaries when configured, "
                        "plus evidence-constrained LLM analysis; full article bodies are unavailable."
                    ),
                    "limitations": (
                        [
                            "Analysis uses headlines and, when available, publisher snippets; "
                            "it does not verify article claims, "
                            "quantify sentiment, or establish investment impact."
                        ]
                        if articles
                        else [
                            "No relevant company-specific news headlines are stored for the last 30 days."
                        ]
                    ),
                },
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:
            self.logger.exception("Market research agent failed")
            return self._create_output(
                False,
                {},
                str(exc),
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
