# AI Investment Desk - Test Queries

This document contains test queries organized by category. Use these to evaluate system capabilities and identify gaps.

---

## ✅ Questions It CAN Answer (Current Capabilities)

### Portfolio Analysis

1. **"What's my portfolio overview?"**
   - Expected Agent: Portfolio Agent
   - Expected Output: Holdings, total value, gains/losses
   - Status: Should work ✓

2. **"What are my biggest positions?"**
   - Expected Agent: Risk Manager Agent
   - Expected Output: Concentration analysis, position weights
   - Status: Should work ✓

3. **"Which holdings are underperforming?"**
   - Expected Agents: Portfolio + Valuation Agents
   - Expected Output: Underperforming holdings with metrics
   - Status: Should work ✓

---

### Valuation & Company Metrics

4. **"What's the P/E ratio for my holdings?"**
   - Expected Agent: Valuation Agent
   - Expected Output: P/E ratios from SEC 10-K
   - Status: Limited - needs SEC fundamentals synced ⚠️
   - Current Result: Returns "unavailable" (SEC data not loaded)

5. **"How profitable is AAPL/MSFT?"** (if in portfolio)
   - Expected Agent: Valuation Agent
   - Expected Output: Profit margins, FCF, earnings
   - Status: Limited - needs SEC data ⚠️
   - Current Result: Works if SEC data is available

6. **"What are the red flags in my portfolio?"**
   - Expected Agent: Risk Manager Agent
   - Expected Output: Concentration risks, high debt ratios
   - Status: Partial - concentration only, not debt analysis ⚠️

---

### Market Context

7. **"What's happening with tech stocks?"**
   - Expected Agent: Market Research Agent
   - Expected Output: News sentiment for portfolio tech companies
   - Status: Should work ✓
   - Note: Only covers companies in portfolio

8. **"What's the macro environment?"**
   - Expected Agent: Macro Agent
   - Expected Output: VIX, Treasury yields, inflation, interest rates
   - Status: Should work ✓
   - Depends on FRED data being synced

9. **"Any recent news on my holdings?"**
   - Expected Agents: Market Research Agent
   - Expected Output: Headlines + sentiment analysis
   - Status: Should work ✓
   - Depends on stored news articles

---

### Cross-Cutting Synthesis

10. **"Should I be worried about my portfolio?"**
    - Expected Agents: All agents combined
    - Expected Output: LLM synthesizes risk assessment
    - Status: Should work ✓

11. **"How does my portfolio compare to macro trends?"**
    - Expected Agents: Risk + Macro Agents synthesized
    - Expected Output: Portfolio vs macro context
    - Status: Should work ✓

---

## ❌ Questions It CANNOT Answer (Current Gaps)

### Arbitrary Ticker Analysis

12. **"Build me a comps table for airlines"**
    - Required Agent: Comps Builder Agent (NOT IMPLEMENTED)
    - Required Data Source: Yahoo Finance / Polygon API (NOT INTEGRATED)
    - Gap: No ability to query arbitrary tickers
    - Status: FAILS ❌

13. **"What's the P/E for Southwest Airlines?"**
    - Required Capability: External ticker lookup
    - Gap: System is portfolio-centric only
    - Status: FAILS ❌
    - Workaround: Add Southwest to portfolio first

14. **"Compare Apple to Microsoft"**
    - Required Capability: Ticker lookup + comps logic
    - Gap: Both must be in portfolio to compare
    - Status: FAILS if not in portfolio ❌
    - Workaround: Add both to portfolio

---

### Industry/Sector Analysis

15. **"Which tech stocks are cheapest?"**
    - Required Agent: Sector Benchmarking Agent (NOT IMPLEMENTED)
    - Required Data: Universe of tech stocks with valuation data
    - Gap: No sector/industry agent
    - Status: FAILS ❌

16. **"How does my energy portfolio compare to peers?"**
    - Required Agent: Sector Analysis Agent (NOT IMPLEMENTED)
    - Gap: Can't benchmark against energy sector
    - Status: FAILS ❌

17. **"What sectors are overvalued right now?"**
    - Required Agent: Sector Analysis Agent (NOT IMPLEMENTED)
    - Gap: Can't perform cross-sector analysis
    - Status: FAILS ❌

---

### Earnings & Transcripts

18. **"What did Apple say in the last earnings call?"**
    - Required Agent: Earnings Transcript Parser (NOT IMPLEMENTED)
    - Required Data: 10-K/10-Q call transcripts
    - Gap: Only SEC filings stored, not transcripts
    - Status: FAILS ❌

19. **"Are margins improving for my holdings?"**
    - Required Capability: Trend analysis over time
    - Gap: Limited to latest SEC facts, no historical trends
    - Status: FAILS ❌
    - Note: Would need time-series margin data

---

### Advanced Research

20. **"Find me the 6 most mispriced stocks in the market"**
    - Required Capability: Universe screening
    - Gap: Can't scan entire market, only portfolio
    - Status: FAILS ❌

21. **"What's the sentiment on semiconductor stocks?"**
    - Required Agents: Sector agent + news aggregation
    - Gap: No sector analysis, news limited to portfolio
    - Status: FAILS ❌

---

### Real-Time Data

22. **"What's the current stock price?"**
    - Current Status: Virtual broker only (sample data)
    - Gap: No real broker integration
    - Status: FAILS (returns sample prices only) ❌
    - Blocked by: Scalable Capital / Binance API integration

23. **"Is there any breaking news?"**
    - Current Status: Only stored articles
    - Gap: No live news streaming
    - Status: FAILS ❌
    - Would require real-time news API

---

## Test Execution Plan

### Phase 1: Run Working Queries
Test that all ✓ marked queries work:
```bash
# Portfolio Analysis
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What'\''s my portfolio overview?", "conversation_id": "test-1"}'

# Market Context
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What'\''s the macro environment?", "conversation_id": "test-2"}'

# Cross-cutting
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Should I be worried about my portfolio?", "conversation_id": "test-3"}'
```

### Phase 2: Identify Limitations
Test queries marked ⚠️ (partial support):
```bash
# These may work partially or return limited data
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What'\''s the P/E ratio for my holdings?", "conversation_id": "test-4"}'
```

### Phase 3: Document Gaps
Try queries marked ❌ and document failures:
```bash
# These should fail - document the error
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Build me a comps table for airlines", "conversation_id": "test-5"}'
```

---

## Gap Analysis Summary

| Category | Implemented | Missing | Priority |
|---|---|---|---|
| Portfolio Analysis | ✓✓✓ | — | — |
| Valuation (portfolio) | ✓ (partial) | SEC data sync | MEDIUM |
| Market Context | ✓✓ | Live news | LOW |
| Comps/Benchmarking | ❌ | Comps Agent, ticker lookup | **HIGH** |
| Sector Analysis | ❌ | Sector Agent | **HIGH** |
| Earnings Transcripts | ❌ | Parser Agent, transcript data | MEDIUM |
| Real Broker Data | ❌ | Scalable Capital/Binance APIs | MEDIUM |
| Universe Screening | ❌ | Data source, screening logic | LOW |

---

## Next Steps to Improve Coverage

### High Priority (High Impact, Medium Effort)
1. **Build Comps Builder Agent** → Unlocks arbitrary ticker queries (airlines, sectors, etc.)
2. **Integrate Yahoo Finance API** → Real valuation data for any ticker
3. **Build Sector Analysis Agent** → Enables sector benchmarking

### Medium Priority (Medium Impact, Medium Effort)
4. **Earnings Transcript Parser** → Answer earnings call questions
5. **Real Broker Integrations** → Replace virtual broker with real prices

### Low Priority (Low Impact, Low Effort)
6. **Sentiment Aggregation** → Cross-sector news analysis
7. **Trend Analysis** → Historical margin/growth trends

---

## Notes

- **Virtual Broker**: Current system uses sample data. Prices are marked as credibility 0.3
- **SEC Data**: Need to sync fundamentals first using dedicated endpoint
- **FRED Data**: Macro indicators depend on successful FRED sync
- **Portfolio-Centric**: System assumes all queries relate to holdings. Arbitrary ticker queries fail.

---

## Quick Reference: Agent Capabilities

| Agent | Can Do | Cannot Do |
|---|---|---|
| **Portfolio** | List holdings, calc gains/losses | Analyze arbitrary tickers |
| **Valuation** | P/E, margins, FCF (if SEC data) | Compare to peers, earnings calls |
| **Market Research** | News on portfolio companies, sentiment | Search entire market, real-time |
| **Macro** | VIX, rates, inflation | Predict future, connect to holdings |
| **Risk Manager** | Concentration, position weights | Industry benchmarking, debt trends |
| **Comps** | ❌ NOT IMPLEMENTED | Everything (needs implementation) |
| **Sector** | ❌ NOT IMPLEMENTED | Everything (needs implementation) |
| **Earnings Parser** | ❌ NOT IMPLEMENTED | Everything (needs implementation) |

