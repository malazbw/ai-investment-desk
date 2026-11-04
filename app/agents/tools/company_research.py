"""On-demand company research tools for companies outside the stored portfolio."""

import logging
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import httpx

from app.brokers.etoro import EtoroAPIError, EtoroMarketDataClient
from app.config import settings
from app.data_sources.news_fetcher import NewsSearcher
from app.data_sources.sec import (
    SEC_COMPANY_FACTS_URL,
    SEC_TICKERS_URL,
    build_ticker_map,
    extract_annual_fact_history,
    extract_company_facts,
)

logger = logging.getLogger(__name__)

COMPANY_ALIASES = {
    "AAPL": ("apple", "apple inc"),
    "MSFT": ("microsoft", "microsoft corporation"),
    "NVDA": ("nvidia", "nvidia corporation"),
}
NON_TICKER_WORDS = {
    "AI", "BUY", "SELL", "HOLD", "PE", "USA", "SEC", "USD", "EUR",
    "CEO", "GDP", "CPI", "VIX", "ETF", "THE", "AND", "FOR", "WITH",
    "WHAT", "WHY", "HOW", "SHOULD", "INVEST", "INTO", "ABOUT",
    "APPLE", "MICROSOFT", "NVIDIA",
}


def extract_company_symbols(message: str) -> List[str]:
    """Find explicit company aliases or ticker-style symbols in a question."""
    normalized = message.casefold()
    symbols = {
        symbol
        for symbol, aliases in COMPANY_ALIASES.items()
        if any(re.search(rf"\b{re.escape(alias)}\b", normalized) for alias in aliases)
    }

    ticker_candidates = re.findall(
        r"(?<![A-Za-z0-9])\$?([A-Z][A-Z0-9.-]{1,5})(?![A-Za-z0-9])",
        message,
    )
    symbols.update(
        ticker
        for ticker in ticker_candidates
        if ticker not in NON_TICKER_WORDS
    )
    return sorted(symbols)


class CompanyResearchTool:
    """Fetch SEC facts, an optional live quote, and recent news without DB writes."""

    def __init__(
        self,
        *,
        user_agent: Optional[str] = None,
        etoro_api_key: Optional[str] = None,
        etoro_user_key: Optional[str] = None,
        newsapi_key: Optional[str] = None,
        sec_transport: Optional[httpx.AsyncBaseTransport] = None,
        etoro_client_factory: Callable[..., EtoroMarketDataClient] = (
            EtoroMarketDataClient
        ),
        news_search: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.user_agent = settings.sec_user_agent if user_agent is None else user_agent
        self.etoro_api_key = (
            settings.etoro_api_key if etoro_api_key is None else etoro_api_key
        )
        self.etoro_user_key = (
            settings.etoro_user_key if etoro_user_key is None else etoro_user_key
        )
        self.newsapi_key = settings.newsapi_key if newsapi_key is None else newsapi_key
        self.sec_transport = sec_transport
        self.etoro_client_factory = etoro_client_factory
        self.news_search = news_search or NewsSearcher.search_newsapi

    async def research(self, symbol: str) -> Dict[str, Any]:
        """Return source-attributed research for one explicit ticker."""
        normalized_symbol = symbol.upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", normalized_symbol):
            raise ValueError(f"Invalid ticker symbol: {symbol}")

        result: Dict[str, Any] = {
            "symbol": normalized_symbol,
            "company_name": self._company_name(normalized_symbol),
            "sources": {},
        }
        await self._fetch_sec_facts(normalized_symbol, result)
        await self._fetch_market_price(normalized_symbol, result)
        await self._fetch_news(normalized_symbol, result)
        self._calculate_metrics(result)
        return result

    @staticmethod
    def _company_name(symbol: str) -> Optional[str]:
        names = COMPANY_ALIASES.get(symbol)
        return names[0].title() if names else None

    async def _fetch_sec_facts(
        self, symbol: str, result: Dict[str, Any]
    ) -> None:
        if not self.user_agent or "@" not in self.user_agent:
            result["sources"]["sec"] = {
                "status": "unavailable",
                "reason": "SEC_USER_AGENT is not configured with a contact email.",
            }
            return

        headers = {
            "User-Agent": self.user_agent.strip(),
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
                transport=self.sec_transport,
            ) as client:
                ticker_response = await client.get(SEC_TICKERS_URL)
                ticker_response.raise_for_status()
                ticker_data = ticker_response.json()
                ticker_map = build_ticker_map(ticker_data)
                cik = ticker_map.get(symbol)
                title = self._find_company_title(ticker_data, symbol)
                if cik is None:
                    result["sources"]["sec"] = {
                        "status": "not_found",
                        "reason": "Ticker is not listed in the SEC company ticker directory.",
                    }
                    return

                result["company_name"] = title or result["company_name"]
                facts_response = await client.get(
                    SEC_COMPANY_FACTS_URL.format(cik=cik)
                )
                facts_response.raise_for_status()
                facts_payload = facts_response.json()
                facts = extract_company_facts(facts_payload)
                annual_history = extract_annual_fact_history(facts_payload)
                result["sources"]["sec"] = {
                    "status": "available" if facts else "no_supported_facts",
                    "cik": cik,
                    "facts": [self._serialize_fact(fact) for fact in facts],
                    "annual_history": {
                        metric: [
                            self._serialize_fact(fact)
                            for fact in observations
                        ]
                        for metric, observations in annual_history.items()
                    },
                    "reason": (
                        None if facts else "No supported annual facts were found."
                    ),
                }
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning(
                "SEC research fetch failed for %s: %s", symbol, type(exc).__name__
            )
            result["sources"]["sec"] = {
                "status": "error",
                "reason": "SEC data request failed; retry later.",
            }

    @staticmethod
    def _serialize_fact(fact: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **fact,
            "period_start": (
                fact["period_start"].isoformat()
                if fact["period_start"]
                else None
            ),
            "period_end": fact["period_end"].isoformat(),
            "filed_date": fact["filed_date"].isoformat(),
            "source": "SEC EDGAR",
        }

    @staticmethod
    def _find_company_title(payload: Any, symbol: str) -> Optional[str]:
        entries = payload.values() if isinstance(payload, dict) else payload
        for item in entries:
            if (
                isinstance(item, dict)
                and str(item.get("ticker", "")).upper() == symbol
            ):
                title = item.get("title")
                return title if isinstance(title, str) else None
        return None

    async def _fetch_market_price(
        self, symbol: str, result: Dict[str, Any]
    ) -> None:
        if not self.etoro_api_key or not self.etoro_user_key:
            result["sources"]["market_price"] = {
                "status": "unavailable",
                "reason": "eToro market-data credentials are not configured.",
            }
            return

        try:
            async with self.etoro_client_factory(
                api_key=self.etoro_api_key,
                user_key=self.etoro_user_key,
            ) as client:
                instrument_id = await client.resolve_instrument_id(symbol)
                if instrument_id is None:
                    result["sources"]["market_price"] = {
                        "status": "not_found",
                        "reason": "No exact active eToro instrument match was found.",
                    }
                    return
                quote = (await client.get_quotes([instrument_id])).get(instrument_id)
                if quote is None:
                    result["sources"]["market_price"] = {
                        "status": "unavailable",
                        "reason": "eToro returned no valid quote.",
                    }
                    return
                result["sources"]["market_price"] = {
                    "status": "available",
                    "price": str(quote.price_usd),
                    "currency": "USD",
                    "date": quote.price_date.isoformat(),
                    "source": "eToro",
                }
        except (EtoroAPIError, ValueError) as exc:
            logger.warning(
                "eToro research quote failed for %s: %s", symbol, type(exc).__name__
            )
            result["sources"]["market_price"] = {
                "status": "error",
                "reason": "eToro market-price request failed; retry later.",
            }

    async def _fetch_news(self, symbol: str, result: Dict[str, Any]) -> None:
        if not self.newsapi_key or self.newsapi_key == "your_newsapi_key_here":
            result["sources"]["news"] = {
                "status": "unavailable",
                "articles": [],
                "reason": "NEWSAPI_KEY is not configured.",
            }
            return

        aliases = COMPANY_ALIASES.get(symbol)
        company_query = aliases[0].upper() if aliases else result["company_name"]
        query = f'"{company_query}" OR {symbol}' if company_query else symbol
        try:
            articles = await self.news_search(query, days=30)
            result["sources"]["news"] = {
                "status": "available" if articles else "no_recent_news",
                "evidence_level": "headline_and_publisher_snippet",
                "articles": [
                    {
                        "headline": article.headline,
                        "description": article.description,
                        "source": article.source,
                        "published_date": article.published_date.isoformat(),
                        "url": article.url,
                    }
                    for article in articles
                ],
                "reason": None if articles else "No recent articles were returned.",
            }
        except RuntimeError as exc:
            logger.warning("News research failed for %s: %s", symbol, exc)
            result["sources"]["news"] = {
                "status": "error",
                "articles": [],
                "reason": str(exc),
            }

    @staticmethod
    def _calculate_metrics(result: Dict[str, Any]) -> None:
        sec_data = result["sources"].get("sec", {})
        facts_by_metric = {
            fact["metric"]: fact for fact in sec_data.get("facts", [])
        }
        annual_history = sec_data.get("annual_history", {})
        price_source = result["sources"].get("market_price", {})
        eps = facts_by_metric.get("diluted_eps")
        pe_ratio = None
        if (
            price_source.get("status") == "available"
            and eps
            and Decimal(eps["value"]) > 0
            and eps["units"].casefold().replace(" ", "")
            in {"usd/share", "usd/shares"}
        ):
            pe_ratio = str(Decimal(price_source["price"]) / Decimal(eps["value"]))

        revenue = facts_by_metric.get("revenue")
        net_income = facts_by_metric.get("net_income")
        net_margin = None
        if (
            revenue
            and net_income
            and revenue["period_end"] == net_income["period_end"]
            and revenue["units"] == net_income["units"] == "USD"
            and Decimal(revenue["value"]) > 0
        ):
            net_margin = str(
                Decimal(net_income["value"])
                / Decimal(revenue["value"])
                * Decimal("100")
            )

        def latest_growth(metric: str) -> Optional[Dict[str, Any]]:
            observations = annual_history.get(metric, [])
            if len(observations) < 2:
                return None
            latest, previous = observations[:2]
            latest_value = Decimal(latest["value"])
            previous_value = Decimal(previous["value"])
            if (
                latest["units"] != previous["units"]
                or previous_value == 0
                or (latest_value < 0 < previous_value)
                or (latest_value > 0 > previous_value)
            ):
                return None
            return {
                "percent": str(
                    (latest_value - previous_value)
                    / abs(previous_value)
                    * Decimal("100")
                ),
                "latest_period_end": latest["period_end"],
                "previous_period_end": previous["period_end"],
                "source": "SEC EDGAR",
            }

        free_cash_flow = None
        operating_cash_flow = facts_by_metric.get("operating_cash_flow")
        capital_expenditures = facts_by_metric.get("capital_expenditures")
        if (
            operating_cash_flow
            and capital_expenditures
            and operating_cash_flow["period_end"]
            == capital_expenditures["period_end"]
            and operating_cash_flow["units"]
            == capital_expenditures["units"]
            == "USD"
        ):
            free_cash_flow = str(
                Decimal(operating_cash_flow["value"])
                - Decimal(capital_expenditures["value"])
            )

        growth = {
            metric: latest_growth(metric)
            for metric in ("revenue", "net_income", "diluted_eps")
        }
        latest_revenue = facts_by_metric.get("revenue")
        fundamental_findings = []
        if latest_revenue:
            revenue_growth = growth["revenue"]
            fundamental_findings.append(
                {
                    "metric": "revenue_growth",
                    "finding": (
                        f"Annual revenue changed by "
                        f"{Decimal(revenue_growth['percent']):.1f}% between fiscal "
                        f"years ending {revenue_growth['previous_period_end']} and "
                        f"{revenue_growth['latest_period_end']}."
                        if revenue_growth
                        else "Comparable prior-year annual revenue was unavailable."
                    ),
                    "evidence": [
                        {
                            "period_end": fact["period_end"],
                            "value": fact["value"],
                            "units": fact["units"],
                            "filed_date": fact["filed_date"],
                            "source": fact["source"],
                        }
                        for fact in annual_history.get("revenue", [])[:2]
                    ],
                    "meaning": (
                        "A year-over-year increase indicates historical sales growth "
                        "for the reported periods, not a forecast."
                    ),
                    "counterpoint": (
                        "Growth rates can be affected by acquisitions, product cycles, "
                        "comparability, and one-off demand."
                    ),
                    "confidence": (
                        "High for arithmetic from the reported annual SEC values."
                        if revenue_growth
                        else "No growth conclusion without two comparable annual values."
                    ),
                }
            )

        if net_margin is not None:
            fundamental_findings.append(
                {
                    "metric": "net_profit_margin",
                    "finding": (
                        f"Latest annual net margin is "
                        f"{Decimal(net_margin):.1f}%."
                    ),
                    "evidence": [
                        {
                            "value": net_income["value"],
                            "period_end": net_income["period_end"],
                            "source": net_income["source"],
                        },
                        {
                            "value": revenue["value"],
                            "period_end": revenue["period_end"],
                            "source": revenue["source"],
                        },
                    ],
                    "meaning": (
                        "This is reported net income per dollar of revenue for that "
                        "fiscal year."
                    ),
                    "counterpoint": (
                        "It is not a forecast and does not by itself show whether "
                        "margins are sustainable."
                    ),
                    "confidence": "High for same-period SEC figures and arithmetic.",
                }
            )

        if free_cash_flow is not None:
            fundamental_findings.append(
                {
                    "metric": "free_cash_flow",
                    "finding": (
                        f"Reported annual free cash flow was USD {free_cash_flow}."
                    ),
                    "evidence": [
                        {
                            "metric": operating_cash_flow["metric"],
                            "value": operating_cash_flow["value"],
                            "period_end": operating_cash_flow["period_end"],
                            "source": operating_cash_flow["source"],
                        },
                        {
                            "metric": capital_expenditures["metric"],
                            "value": capital_expenditures["value"],
                            "period_end": capital_expenditures["period_end"],
                            "source": capital_expenditures["source"],
                        },
                    ],
                    "meaning": (
                        "This approximates operating cash flow less reported capital "
                        "expenditures for the same fiscal year."
                    ),
                    "counterpoint": (
                        "It does not show future cash generation, and definitions can "
                        "vary from company-adjusted measures."
                    ),
                    "confidence": "High for the same-period reported inputs and subtraction.",
                }
            )

        result["valuation"] = {
            "pe_ratio": pe_ratio,
            "pe_ratio_basis": (
                "On-demand eToro USD quote divided by latest annual diluted EPS"
                if pe_ratio is not None
                else None
            ),
            "net_profit_margin_percent": net_margin,
            "fundamentals_status": result["sources"].get("sec", {}).get("status"),
            "price_status": price_source.get("status"),
            "latest_annual_facts": facts_by_metric,
            "year_over_year_growth": growth,
            "free_cash_flow": free_cash_flow,
        }
        result["fundamental_analysis"] = {
            "findings": fundamental_findings,
            "valuation_interpretation": (
                {
                    "finding": (
                        f"The trailing P/E is {Decimal(pe_ratio):.1f}."
                    ),
                    "evidence": [
                        {
                            "price": price_source["price"],
                            "currency": price_source["currency"],
                            "price_date": price_source["date"],
                            "source": price_source["source"],
                        },
                        {
                            "diluted_eps": eps["value"],
                            "period_end": eps["period_end"],
                            "filed_date": eps["filed_date"],
                            "source": eps["source"],
                        },
                    ],
                    "meaning": (
                        "At this quote, investors pay that many dollars per dollar "
                        "of the latest reported annual diluted earnings."
                    ),
                    "counterpoint": (
                        "A trailing P/E does not establish fair value. It depends on "
                        "future earnings durability and requires peer and historical "
                        "comparisons to judge relative valuation."
                    ),
                    "confidence": "High for the arithmetic; low for a cheap/expensive judgment.",
                }
                if pe_ratio is not None
                else {
                    "finding": "A trailing P/E cannot be calculated from current sources.",
                    "evidence": [
                        f"Price status: {price_source.get('status')}.",
                        f"SEC facts status: {sec_data.get('status')}.",
                    ],
                    "meaning": "Do not infer a valuation multiple when either input is missing.",
                    "counterpoint": "An unavailable P/E is a data gap, not evidence about value.",
                    "confidence": "High that a required source is missing.",
                }
            ),
            "missing": [
                "Forward earnings estimates.",
                "Comparable peer and historical valuation multiples.",
                "Full news articles and independently verified claims.",
            ],
        }
