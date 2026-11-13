# News Agent Implementation Plan (Tier 2: Real-Time News & Sentiment)

## Overview
Build a News Agent that scans breaking financial news, press releases, and editorial commentary, filtering by ticker symbols and providing market sentiment analysis.

---

## Task 1: Core News Fetching & Filtering

### What to Build
- Fetch real-time news from NewsAPI for a given ticker
- Filter articles for **investment relevance** (not celebrity gossip or unrelated news)
- Return structured list of relevant articles with metadata

### Inputs
```python
ticker: str  # e.g., "TSLA", "MSFT", "AMZN"
days: int    # e.g., 7 (last 7 days)
limit: int   # e.g., 20 (max articles to return)
```

### Outputs
```python
{
    "ticker": "TSLA",
    "status": "success",
    "total_found": 15,
    "articles": [
        {
            "title": "Tesla stock drops 4% on Q3 delivery miss",
            "source": "Reuters",
            "url": "https://...",
            "published_at": "2026-11-13T10:30:00Z",
            "snippet": "Tesla reported...",
            "relevance_score": 0.95,  # 0-1, higher = more investment relevant
            "ticker_mentions": ["TSLA"]
        },
        ...
    ],
    "fetched_at": "2026-11-13T..."
}
```

### Implementation Details
- **News Source**: Use NewsAPI (already integrated in codebase)
- **Relevance Filter**: Keywords like "earnings", "revenue", "profit", "analyst", "guidance", "stock", "market", etc.
- **Calculation**: Score based on:
  - How many investment keywords in title/snippet
  - How many times ticker mentioned
  - Source credibility (Reuters > blog)
- **Deduplication**: Remove duplicate articles from different sources
- **Date Filtering**: Only articles from last N days

### Success Criteria
✅ Fetch 15-20 relevant articles for a ticker  
✅ Filter out non-investment news (sports, politics, etc.)  
✅ Return relevance_score for each article  
✅ Handle tickers with no news (empty array, not error)  
✅ Handle invalid tickers gracefully  

---

## Task 2: Sentiment Analysis & Aggregation

### What to Build
- Analyze sentiment (positive/negative/neutral) of each article
- Aggregate sentiment across all articles into summary metrics
- Create findings for LLM consumption

### Inputs
```python
articles: List[Dict]  # From Task 1
ticker: str
```

### Outputs
```python
{
    "ticker": "AMZN",
    "sentiment_summary": {
        "positive_count": 8,
        "negative_count": 3,
        "neutral_count": 4,
        "overall_sentiment": "positive",  # majority sentiment
        "sentiment_score": 0.68,  # -1 (all negative) to +1 (all positive)
        "confidence": 0.85  # based on article count & consistency
    },
    "top_themes": [
        {"theme": "Earnings Beat", "count": 5, "sentiment": "positive"},
        {"theme": "Competition", "count": 3, "sentiment": "negative"},
        {"theme": "Regulation", "count": 2, "sentiment": "neutral"}
    ],
    "findings": [
        {
            "claim": "Amazon stock momentum is positive with 8 bullish articles in the past week",
            "source": {
                "source_type": "NEWS_ARTICLES",
                "source_name": "Financial News Aggregate",
                "credibility_score": 0.75,
                "url": None,
                "fetched_at": "2026-11-13T..."
            },
            "evidence_level": "secondary",
            "confidence_score": 0.75,
            "metadata": {
                "article_count": 15,
                "positive": 8,
                "negative": 3,
                "neutral": 4
            }
        }
    ]
}
```

### Implementation Details
- **Sentiment Analysis Method**: Use Claude LLM to score sentiment (already have API)
  - Input: article title + snippet
  - Output: score (-1 to +1) + category (positive/negative/neutral)
- **Batch Processing**: Send 5-10 articles per Claude API call (cheaper, faster)
- **Theme Detection**: Use Claude to extract 2-3 key themes from each article
- **Aggregate Scoring**: 
  - `sentiment_score = (positive_count - negative_count) / total_count`
  - `confidence = min(1.0, article_count / 10)` (more articles = higher confidence)
- **Finding Creation**: Generate structured Finding objects with source attribution

### Success Criteria
✅ Score each article as positive/negative/neutral  
✅ Aggregate into summary metrics  
✅ Calculate confidence based on article count  
✅ Extract top themes  
✅ Create source-attributed findings  
✅ Handle edge cases (1 article, 100 articles, no articles)  

---

## Task 3: News Agent Integration & Query Handling

### What to Build
- Create NewsAgent class that orchestrates Tasks 1 & 2
- Integrate into agent router (respond to news queries)
- Return findings ready for LLM synthesis

### Inputs (from Chat Endpoint)
```python
{
    "user_message": "Why is Tesla stock down 4% today?",
    "context": AgentContext(...)
}
```

### Outputs (to LLM for Synthesis)
```python
{
    "agent_name": "news",
    "success": True,
    "data": {
        "findings": [...],  # From Task 2
        "assessment": {
            "finding": "Recent Tesla news shows mixed sentiment...",
            "evidence": ["8 bullish articles about...", "3 bearish articles about..."],
            "meaning": "Market is uncertain about Tesla's near-term direction",
            "counterpoint": "Past news doesn't predict future moves",
            "confidence": "Medium - based on 15 recent articles",
            "missing": ["CEO commentary", "Analyst upgrades/downgrades", "Options market signals"]
        },
        "ticker": "TSLA",
        "article_count": 15,
        "sentiment_summary": {...},
        "fetched_at": "2026-11-13T..."
    }
}
```

### Implementation Details
- **Class**: `NewsAgent(BaseAgent)`
- **Entry Point**: `async def execute(context: AgentContext) -> AgentOutput`
- **Query Detection**: Look for keywords like "news", "sentiment", "why is X stock", "headlines", "announcement"
- **Flow**:
  1. Extract ticker from user message
  2. Call Task 1: Fetch & filter articles
  3. Call Task 2: Analyze sentiment & create findings
  4. Create assessment with Evidence/Meaning/Confidence/Missing
  5. Return AgentOutput with findings + assessment
- **Error Handling**:
  - Invalid ticker → return error in AgentOutput
  - No articles found → return empty findings + explanation
  - API rate limit → return cached data or error

### Success Criteria
✅ Create NewsAgent class inheriting from BaseAgent  
✅ Detect news-related queries from user message  
✅ Extract ticker correctly  
✅ Orchestrate Tasks 1 & 2  
✅ Return structured findings with source attribution  
✅ Generate meaningful assessment  
✅ Integrate with agent router (router selects it for news queries)  
✅ End-to-end test: "Why is Amazon stock down today?" → News Agent runs → LLM synthesizes answer  

---

## Implementation Order

1. **Start with Task 1** (News Fetching & Filtering)
   - Implement NewsAPI integration
   - Build relevance scoring
   - Test with real ticker data

2. **Then Task 2** (Sentiment Analysis)
   - Add Claude sentiment scoring
   - Build aggregation logic
   - Create findings objects

3. **Finally Task 3** (Agent Integration)
   - Create NewsAgent class
   - Wire up to router
   - End-to-end testing

---

## Files to Create/Modify

**New Files:**
- `app/agents/news_agent.py` — NewsAgent class (Task 3)
- `app/data_sources/news_processor.py` — Sentiment analysis & aggregation (Task 2)

**Modify:**
- `app/data_sources/newsapi.py` — Enhance for Task 1 (filtering, relevance scoring)
- `app/agents/router.py` — Add news agent to routing prompt
- `app/routes.py` — Register NewsAgent in agents dict

---

## Testing Examples

### Test 1: Basic News Fetch
```python
# Task 1 output
result = await newsapi_fetcher.fetch_ticker_news("TSLA", days=7, limit=20)
assert result["status"] == "success"
assert len(result["articles"]) > 0
assert all("relevance_score" in a for a in result["articles"])
```

### Test 2: Sentiment Analysis
```python
# Task 2 output
sentiment = await sentiment_analyzer.analyze_articles(articles, "TSLA")
assert "sentiment_summary" in sentiment
assert "findings" in sentiment
assert sentiment["sentiment_summary"]["overall_sentiment"] in ["positive", "negative", "neutral"]
```

### Test 3: End-to-End
```python
# Task 3: Full agent test
result = await news_agent.execute(
    context=AgentContext(
        user_message="Why is Tesla stock down 4% today?",
        metadata={...}
    )
)
assert result.success == True
assert len(result.data["findings"]) > 0
assert "assessment" in result.data
```

---

## Notes

- **Reuse Existing**: We already have NewsAPI integration in `app/data_sources/newsapi.py` - enhance it rather than rewrite
- **Source Attribution**: Every finding must include Finding + SourceRef with credibility_score
- **No Router/Orchestrator Needed Yet**: Just get the agent working; router will auto-detect it based on keywords
- **One Task at a Time**: Complete & test Task 1 before moving to Task 2

