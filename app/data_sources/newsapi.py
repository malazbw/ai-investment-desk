"""Live news fetcher using NewsAPI"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class NewsAPIFetcher:
    """Fetch live news from NewsAPI"""

    BASE_URL = "https://newsapi.org/v2"

    # Map tickers to search terms for better results
    TICKER_KEYWORDS = {
        "NVDA": "Nvidia OR NVDA",
        "AAPL": "Apple OR AAPL",
        "MSFT": "Microsoft OR MSFT",
        "TSLA": "Tesla OR TSLA",
        "AMZN": "Amazon OR AMZN",
        "GOOGL": "Google OR Alphabet OR GOOGL",
        "META": "Meta OR Facebook OR META",
        "AMD": "AMD OR Advanced Micro",
    }

    @classmethod
    async def fetch_ticker_news(
        cls,
        ticker: str,
        days: int = 7,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Fetch live news for a specific ticker"""

        if not settings.newsapi_key:
            return {
                "ticker": ticker,
                "status": "error",
                "reason": "NEWSAPI_KEY not configured",
                "articles": []
            }

        try:
            # Build search query
            search_term = cls.TICKER_KEYWORDS.get(ticker.upper(), ticker)

            # Only search recent articles
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{cls.BASE_URL}/everything",
                    params={
                        "q": search_term,
                        "sortBy": "publishedAt",
                        "language": "en",
                        "from": from_date,
                        "apiKey": settings.newsapi_key,
                        "pageSize": limit,
                    }
                )

                if response.status_code != 200:
                    return {
                        "ticker": ticker,
                        "status": "error",
                        "reason": f"API returned {response.status_code}",
                        "articles": []
                    }

                data = response.json()

                if data.get("status") != "ok":
                    return {
                        "ticker": ticker,
                        "status": "error",
                        "reason": data.get("message", "Unknown error"),
                        "articles": []
                    }

                # Filter for investment-relevant articles
                articles = cls._filter_investment_articles(
                    data.get("articles", []),
                    ticker
                )

                return {
                    "ticker": ticker,
                    "status": "success",
                    "total_found": data.get("totalResults", 0),
                    "articles": articles,
                    "fetched_at": datetime.utcnow().isoformat()
                }

        except httpx.TimeoutException:
            return {
                "ticker": ticker,
                "status": "error",
                "reason": "API request timeout",
                "articles": []
            }
        except Exception as e:
            logger.exception(f"Failed to fetch news for {ticker}")
            return {
                "ticker": ticker,
                "status": "error",
                "reason": str(e),
                "articles": []
            }

    @staticmethod
    def _filter_investment_articles(articles: List[Dict], ticker: str) -> List[Dict]:
        """Filter articles for investment relevance"""

        investment_keywords = {
            "earnings", "revenue", "profit", "guidance", "forecast",
            "stock", "price", "valuation", "pe ratio", "dividend",
            "acquisition", "merger", "partnership", "competition",
            "analyst", "rating", "upgrade", "downgrade", "target",
            "quarterly", "annual", "results", "financial", "report",
            "market", "sector", "industry", "ipo", "outlook",
        }

        filtered = []

        for article in articles:
            title = (article.get("title") or "").lower()
            description = (article.get("description") or "").lower()
            content = f"{title} {description}"

            # Check for investment-relevant keywords
            if any(kw in content for kw in investment_keywords):
                filtered.append({
                    "headline": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "published_date": article.get("publishedAt", ""),
                    "image_url": article.get("urlToImage"),
                    "content": article.get("content", ""),
                    "relevance_score": NewsAPIFetcher._calculate_relevance(content, ticker),
                })

        # Sort by relevance and recency
        filtered.sort(
            key=lambda x: (
                -x["relevance_score"],
                -datetime.fromisoformat(
                    x["published_date"].replace("Z", "+00:00")
                ).timestamp()
            )
        )

        return filtered

    @staticmethod
    def _calculate_relevance(content: str, ticker: str) -> float:
        """Calculate relevance score for article"""

        score = 0.5  # Base score

        # Boost for ticker mentions
        if ticker.lower() in content:
            score += 0.3

        # Boost for company name mentions
        if ticker in ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]:
            company_names = {
                "AAPL": "apple",
                "MSFT": "microsoft",
                "NVDA": "nvidia",
                "TSLA": "tesla",
                "AMZN": "amazon",
            }
            if company_names.get(ticker, "").lower() in content:
                score += 0.2

        # High boost for critical keywords
        critical_keywords = {"earnings", "guidance", "acquisition", "analyst"}
        if any(kw in content for kw in critical_keywords):
            score += 0.2

        return min(score, 1.0)
