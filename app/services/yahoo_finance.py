"""
Yahoo Finance service for fetching stock fundamentals
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooFinanceNews:
    """Get news from Yahoo Finance (free, no API key)"""

    @staticmethod
    async def get_news(symbol: str, limit: int = 10) -> Dict:
        """
        Fetch news for a stock symbol from Yahoo Finance.

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            limit: Max number of articles (default 10)

        Returns:
            Dict with news articles
        """
        try:
            logger.info(f"[Yahoo Finance News] Fetching news for {symbol}")

            ticker = yf.Ticker(symbol)
            news = ticker.news

            if not news:
                logger.warning(f"[Yahoo Finance News] No news found for {symbol}")
                return {"ticker": symbol, "articles": [], "status": "no_news"}

            # Limit results
            news = news[:limit]

            # Parse news articles
            articles = []
            for article in news:
                content = article.get("content", {})
                finance = content.get("finance", {})
                stock_tickers = finance.get("stockTickers", [])
                related_tickers = [t.get("symbol") for t in stock_tickers if t.get("symbol")]

                articles.append({
                    "headline": content.get("title", ""),
                    "description": content.get("summary", "") or content.get("description", ""),
                    "url": content.get("canonicalUrl", {}).get("url") or content.get("clickThroughUrl", {}).get("url") or "",
                    "source": content.get("provider", {}).get("displayName", "Yahoo Finance"),
                    "published_date": content.get("pubDate") or content.get("displayTime"),
                    "related_tickers": related_tickers,
                    "content_type": content.get("contentType", "ARTICLE"),
                    "thumbnail_url": content.get("thumbnail", {}).get("originalUrl") if content.get("thumbnail") else None,
                })

            logger.info(f"[Yahoo Finance News] Found {len(articles)} articles for {symbol}")
            return {
                "ticker": symbol,
                "articles": articles,
                "status": "success",
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"[Yahoo Finance News] Error fetching news for {symbol}: {e}")
            return {"ticker": symbol, "articles": [], "status": "error", "error": str(e)}


class YahooFinanceService:
    """Fetch fundamental data from Yahoo Finance using yfinance library"""

    def __init__(self):
        """Initialize Yahoo Finance service"""
        pass

    async def get_fundamentals(self, symbol: str) -> Dict:
        """
        Fetch fundamental data for a stock symbol.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Dict with fundamental metrics
        """
        try:
            logger.info(f"[Yahoo Finance] Fetching fundamentals for {symbol}")

            # Fetch ticker data from Yahoo Finance
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or info.get("regularMarketPrice") is None:
                logger.warning(f"[Yahoo Finance] No data returned for {symbol}")
                return {"error": "No data available"}

            # Parse and format fundamentals
            fundamentals = self._parse_fundamentals(symbol, info)
            logger.info(f"[Yahoo Finance] Successfully fetched fundamentals for {symbol}")
            return fundamentals

        except Exception as e:
            logger.error(f"[Yahoo Finance] Error fetching {symbol}: {e}")
            return {"error": str(e)}

    async def get_multiple(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch fundamentals for multiple symbols.

        Args:
            symbols: List of stock ticker symbols

        Returns:
            Dict mapping symbols to their fundamentals
        """
        results = {}
        for symbol in symbols:
            results[symbol] = await self.get_fundamentals(symbol)
        return results

    def _parse_fundamentals(self, symbol: str, info: Dict) -> Dict:
        """
        Parse yfinance response into clean fundamentals dict.

        Args:
            symbol: Stock symbol
            info: Raw yfinance info dict

        Returns:
            Cleaned fundamentals dict
        """
        def safe_get(key, default=None):
            """Safely get value from info dict"""
            return info.get(key, default)

        return {
            "symbol": symbol,
            "valuation": {
                "pe_trailing": safe_get("trailingPE"),
                "pe_forward": safe_get("forwardPE"),
                "price_to_book": safe_get("priceToBook"),
                "market_cap": safe_get("marketCap"),
                "book_value": safe_get("bookValue"),
                "peg_ratio": safe_get("pegRatio"),
            },
            "earnings": {
                "eps_trailing": safe_get("trailingEps"),
                "eps_current_year": safe_get("epsCurrentYear"),
                "eps_forward": safe_get("epsForward"),
                "revenue_per_share": safe_get("revenuePerShare"),
            },
            "profitability": {
                "profit_margin": safe_get("profitMargins"),
                "operating_margin": safe_get("operatingMargins"),
                "gross_margin": safe_get("grossMargins"),
                "return_on_assets": safe_get("returnOnAssets"),
                "return_on_equity": safe_get("returnOnEquity"),
            },
            "financial_health": {
                "debt_to_equity": safe_get("debtToEquity"),
                "current_ratio": safe_get("currentRatio"),
                "quick_ratio": safe_get("quickRatio"),
            },
            "price_action": {
                "current_price": safe_get("regularMarketPrice"),
                "fifty_two_week_high": safe_get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": safe_get("fiftyTwoWeekLow"),
                "beta": safe_get("beta"),
                "fifty_two_week_change": safe_get("fiftyTwoWeekChange"),
            },
            "income": {
                "dividend_yield": safe_get("dividendYield"),
                "trailing_annual_dividend": safe_get("trailingAnnualDividendRate"),
                "five_year_avg_dividend_yield": safe_get("fiveYearAvgDividendYield"),
            },
            "growth": {
                "revenue_growth": safe_get("revenueGrowth"),
                "earnings_growth": safe_get("earningsGrowth"),
            },
            "fetched_at": datetime.utcnow().isoformat(),
        }
