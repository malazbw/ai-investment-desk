"""
Fetch news for portfolio stocks from free sources
"""
import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class NewsArticle:
    """Represents a news article"""
    def __init__(self, symbol: str, headline: str, url: str, source: str, published_date: datetime):
        self.symbol = symbol
        self.headline = headline
        self.url = url
        self.source = source
        self.published_date = published_date


class NewsSearcher:
    """Search for news using free sources"""

    @staticmethod
    async def search_newsapi(query: str, days: int = 7) -> List[NewsArticle]:
        """
        Search NewsAPI.org (free tier, 100 requests/day)
        Returns news articles for the query
        """
        try:
            from app.config import settings

            url = "https://newsapi.org/v2/everything"

            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            params = {
                "q": query,
                "from": from_date,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 10,
            }

            # Add API key if available
            if settings.newsapi_key and settings.newsapi_key != "your_newsapi_key_here":
                params["apiKey"] = settings.newsapi_key

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            articles = []
            for article in data.get("articles", []):
                try:
                    published = datetime.fromisoformat(
                        article["publishedAt"].replace("Z", "+00:00")
                    )
                    articles.append(NewsArticle(
                        symbol=query.upper(),
                        headline=article["title"],
                        url=article["url"],
                        source=article.get("source", {}).get("name", "NewsAPI"),
                        published_date=published
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing article: {e}")
                    continue

            return articles

        except Exception as e:
            logger.error(f"Error fetching from NewsAPI: {e}")
            return []

    @staticmethod
    async def search_ycombinator_news():
        """
        Fallback: Search Hacker News for tech stocks
        Free, no API key needed
        """
        try:
            # Hacker News API (free, no auth)
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                story_ids = response.json()[:30]  # Top 30

            articles = []
            for story_id in story_ids[:10]:  # Fetch details for top 10
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    item = await client.get(item_url)
                    if item.status_code == 200:
                        data = item.json()
                        if data.get("type") == "story" and data.get("url"):
                            articles.append(NewsArticle(
                                symbol="TECH",  # Placeholder
                                headline=data.get("title", ""),
                                url=data.get("url", ""),
                                source="HackerNews",
                                published_date=datetime.fromtimestamp(data.get("time", 0))
                            ))

            return articles

        except Exception as e:
            logger.error(f"Error fetching from HackerNews: {e}")
            return []


async def fetch_news_for_stocks(symbols: List[str], days: int = 7) -> Dict[str, List[NewsArticle]]:
    """
    Fetch news for multiple stock symbols

    Args:
        symbols: List of stock symbols (e.g., ["AAPL", "MSFT"])
        days: How many days back to search

    Returns:
        Dict mapping symbol to list of news articles
    """
    results = {}

    for symbol in symbols:
        logger.info(f"Fetching news for {symbol}...")

        # Try NewsAPI first
        articles = await NewsSearcher.search_newsapi(symbol, days=days)

        if not articles:
            logger.warning(f"No news found for {symbol} on NewsAPI, trying alternatives...")
            # Could add other sources here later

        results[symbol] = articles
        logger.info(f"Found {len(articles)} articles for {symbol}")

    return results
