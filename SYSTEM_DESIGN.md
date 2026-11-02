# AI Investment Desk - System Design Document

## Executive Summary

AI Investment Desk is a multi-agent AI platform that consolidates user portfolios across brokers and provides intelligent portfolio analysis through a conversational chatbot. Instead of pre-fetching and caching all data, the system uses specialized agents that fetch real-time data on-demand based on user questions.

---

## Current System Architecture

### Overview

```
┌────────────────────────────────────────────┐
│            Chat API (FastAPI)              │
│  POST /api/chat/message                    │
└────────┬─────────────────────────────────┬─┘
         │                                 │
         ▼                                 ▼
    ┌─────────────────────────────────────────┐
    │   Agent Orchestrator/Router             │
    │  (Routes questions to agents)           │
    └─────────────────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┬──────────┐
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐┌──────────┐┌──────────┐┌────────┐┌──────────┐
│Portfolio│Market    │Valuation │Risk     │Macro     │
│Agent    │Research  │Agent     │Manager  │Context   │
│         │Agent     │          │Agent    │Agent     │
│Queries  │Calls:    │Calls:    │Validates│Pulls:    │
│DB       │- News    │- Financial│against  │- VIX     │
│         │  APIs    │  APIs    │limits   │- Rates   │
│         │- Analyst │- eToro   │         │- CPI     │
│         │- SEC     │- Yahoo   │         │          │
└────┬────┘└───┬─────┘└────┬────┘└───┬────┘└────┬────┘
     │         │           │         │          │
     │         ▼           ▼         ▼          ▼
     │    ┌────────────────────────────────┐
     │    │   External APIs (Real-time)    │
     │    │ - News APIs                    │
     │    │ - eToro API (prices, holdings) │
     │    │ - Yahoo Finance                │
     │    │ - SEC Edgar                    │
     │    │ - FRED (macro)                 │
     │    │ - Frankfurter (FX)             │
     └────┤ - Binance API                  │
          └────────────────────────────────┘
               │
               ▼
          ┌──────────────────┐
          │   Database       │
          │  (Holdings,      │
          │   Transactions,  │
          │   Historical     │
          │   Snapshots)     │
          └──────────────────┘
               │
               ▼
          ┌──────────────────┐
          │   Claude API     │
          │  (Synthesizes    │
          │   all data)      │
          └──────────────────┘
```

### Data Flow

1. **User Input** → Chat endpoint receives question
2. **Agent Router** → Determines which agents to invoke
3. **Agents Execute in Parallel** → Each fetches relevant data:
   - Portfolio Agent: queries database
   - Market Research Agent: calls news/analyst APIs
   - Valuation Agent: builds models from public data
   - Risk Manager Agent: evaluates constraints
   - Macro Context Agent: fetches economic indicators
4. **Data Aggregation** → Combine all agent outputs
5. **Claude Processing** → LLM synthesizes analysis
6. **Response** → Return to user via chat interface

---

## Current Implementation Status

### ✅ Implemented (Core Foundation)

1. **Database Layer** (`app/models.py`)
   - Asset, Holding, Transaction models
   - Price, PortfolioSnapshot tracking
   - MacroIndicator, ExchangeRate models
   - CompanyNews model

2. **Services Layer** (`app/services.py`)
   - PortfolioService (CRUD operations)
   - MacroDataService (FRED integration)
   - ExchangeRateService (Frankfurter integration)
   - NewsService (news fetching)

3. **Data Pipeline** (`app/scheduler.py`)
   - Background scheduler for periodic updates
   - Jobs: exchange rates, macro indicators, news
   - Cron-based execution

4. **API Endpoints** (`app/routes.py`)
   - Portfolio endpoints: `/api/portfolio/summary`, `/api/portfolio/holdings`
   - Macro endpoints: `/api/macro/*`
   - Exchange rate endpoints: `/api/exchange-rates/*`
   - News endpoints: `/api/news/*`
   - Virtual broker sync: `/api/portfolio/sync/virtual`

5. **Broker Integration Start**
   - VirtualBroker (testing)
   - Abstract broker interface

---

### ❌ Not Implemented (Phase 1 Requirements)

#### 1. **Agent System** (Core - HIGH PRIORITY)
   - [ ] Agent base class/interface
   - [ ] Agent Router/Orchestrator
   - [ ] Portfolio Agent (queries holdings)
   - [ ] Market Research Agent (news + analyst)
   - [ ] Valuation Agent (financial models)
   - [ ] Risk Manager Agent (constraints)
   - [ ] Macro Context Agent (economic data)
   - [ ] Agent execution framework (parallel execution)

#### 2. **Chat Interface** (Frontend - HIGH PRIORITY)
   - [ ] Web chat UI component
   - [ ] Conversation history management
   - [ ] Message streaming
   - [ ] Error handling UI

#### 3. **Claude Integration** (Core - HIGH PRIORITY)
   - [ ] Claude API client wrapper
   - [ ] System prompts per agent
   - [ ] Context builder (format agent outputs for Claude)
   - [ ] Response parsing and formatting

#### 4. **eToro Integration** (Data Source - HIGH PRIORITY)
   - [ ] eToro API client
   - [ ] Authentication/API key management
   - [ ] Real-time price fetching (stocks, crypto)
   - [ ] Holdings synchronization
   - [ ] News/market info from eToro

#### 5. **Real Broker Integrations** (Data Source - MEDIUM PRIORITY)
   - [ ] Scalable Capital API client
   - [ ] Binance API client (already have partially)
   - [ ] Authentication per broker
   - [ ] Holdings sync across brokers

#### 6. **Enhanced Data Sources** (Data Source - MEDIUM PRIORITY)
   - [ ] Financial modeling API (e.g., Alpha Vantage, IEX Cloud)
   - [ ] SEC Edgar integration (for 10-K, 10-Q parsing)
   - [ ] Better analyst rating sources
   - [ ] Real-time news aggregation

#### 7. **Context Builder** (Core - MEDIUM PRIORITY)
   - [ ] Aggregate agent outputs
   - [ ] Format for Claude consumption
   - [ ] Relevance scoring/filtering
   - [ ] Context size optimization

---

## Implementation Roadmap

### Phase 1: MVP Chatbot (Weeks 1-4)

**Goal:** User can ask about portfolio, get AI-driven analysis

#### Week 1: Agent Framework
- [ ] Design agent base class
- [ ] Implement agent router/orchestrator
- [ ] Setup parallel execution (async)
- [ ] Error handling & logging

#### Week 2: Portfolio Agent + Claude Integration
- [ ] Build Portfolio Agent (queries DB)
- [ ] Integrate Claude API
- [ ] Create system prompts
- [ ] Build context formatter

#### Week 3: eToro Integration
- [ ] Research eToro API
- [ ] Build eToro client
- [ ] Real-time price fetching
- [ ] Test with sample data

#### Week 4: Chat Interface + Integration
- [ ] Build simple web chat UI
- [ ] Connect to backend
- [ ] End-to-end testing
- [ ] Deploy MVP

### Phase 2: Enhanced Analysis (Weeks 5-8)

**Goal:** More sophisticated agents for deeper analysis

#### Week 5: Market Research Agent
- [ ] News aggregation
- [ ] Sentiment analysis
- [ ] Analyst rating sources
- [ ] Competitive intelligence

#### Week 6: Valuation Agent
- [ ] Financial data APIs
- [ ] DCF model builder
- [ ] Comparable analysis
- [ ] Valuation scoring

#### Week 7: Risk Manager Agent
- [ ] Risk calculation engine
- [ ] Portfolio stress testing
- [ ] Constraint validation
- [ ] Diversification analysis

#### Week 8: Macro Context Agent
- [ ] Enhanced macro data
- [ ] Macro-to-portfolio correlation
- [ ] Scenario analysis
- [ ] Market regime detection

### Phase 3: Real Broker Integrations (Weeks 9-12)

**Goal:** Production-ready multi-broker support

- [ ] Scalable Capital OAuth
- [ ] Binance secure key management
- [ ] Holdings reconciliation
- [ ] Multi-broker portfolio view

### Phase 4: Autonomous Trading (Future)

**Goal:** AI can execute trades with allocated capital

- [ ] Agent capital allocation model
- [ ] Trade execution framework
- [ ] Backtesting engine
- [ ] Risk controls & safeguards

---

## Key Components to Build

### 1. Agent Framework (`app/agents/`)

```
agents/
├── __init__.py
├── base.py                 # BaseAgent abstract class
├── router.py               # AgentRouter/Orchestrator
├── portfolio_agent.py      # Portfolio analysis
├── market_research_agent.py # News & analyst
├── valuation_agent.py      # Financial models
├── risk_manager_agent.py   # Risk analysis
├── macro_agent.py          # Economic data
└── execution.py            # Parallel execution
```

### 2. Claude Integration (`app/llm/`)

```
llm/
├── __init__.py
├── client.py               # Claude API wrapper
├── prompts.py              # System prompts per agent
├── context_builder.py      # Format agent outputs
└── models.py               # Response models
```

### 3. eToro Integration (`app/brokers/etoro/`)

```
brokers/etoro/
├── __init__.py
├── client.py               # eToro API client
├── auth.py                 # Authentication
├── prices.py               # Real-time prices
├── holdings.py             # Portfolio sync
└── news.py                 # Market info
```

### 4. Chat Interface (Frontend)

```
frontend/
├── src/
│  ├── components/
│  │  ├── ChatWindow.tsx
│  │  ├── MessageList.tsx
│  │  ├── InputBox.tsx
│  │  └── PortfolioSummary.tsx
│  ├── pages/
│  │  ├── ChatPage.tsx
│  │  └── DashboardPage.tsx
│  └── services/
│     └── chatApi.ts        # Chat endpoint client
```

### 5. Chat Endpoint (`app/routes.py` - new)

```python
# New route
@router.post("/api/chat/message")
async def chat(message: ChatMessage, db: Session = Depends(get_db)):
    """
    Main chat endpoint
    1. Route message to agents
    2. Fetch real-time data
    3. Send to Claude
    4. Return response
    """
    # Orchestrator flow
    agents_to_run = router.decide_agents(message)
    agent_outputs = await asyncio.gather(*[
        agent.execute(message, db) for agent in agents_to_run
    ])
    context = context_builder.format(agent_outputs)
    response = await claude.analyze(message, context)
    return response
```

---

## eToro Integration Details

### Why eToro?

- Real-time stock & crypto prices
- Market news & sentiment
- Copy trading insights
- Demo account for testing
- Good API documentation

### eToro API Capabilities

1. **Prices** - Real-time stock & crypto quotes
2. **Holdings** - User portfolio sync
3. **News** - Market news feed
4. **Research** - Company info, analyst ratings
5. **Watchlists** - Custom asset tracking

### Implementation Plan

```python
# app/brokers/etoro/client.py

class eToroBroker:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = aiohttp.ClientSession()
    
    async def get_prices(self, symbols: List[str]) -> Dict[str, Price]:
        """Fetch real-time prices for stocks/crypto"""
        
    async def get_holdings(self) -> List[Holding]:
        """Get user portfolio"""
        
    async def get_news(self, symbol: str) -> List[NewsArticle]:
        """Get recent news for asset"""
        
    async def get_fundamentals(self, symbol: str) -> CompanyFundamentals:
        """Get company/asset fundamentals"""
```

---

## Database Schema Additions

### New Tables Needed

```sql
-- Agent state tracking
CREATE TABLE agent_cache (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50),
    query_key VARCHAR(255),
    result JSONB,
    cached_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- Chat history
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    message_text TEXT,
    response_text TEXT,
    timestamp TIMESTAMP,
    agents_used VARCHAR[] -- which agents handled this
);

-- Agent performance metrics
CREATE TABLE agent_metrics (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50),
    execution_time_ms INTEGER,
    api_calls INTEGER,
    success BOOLEAN,
    timestamp TIMESTAMP
);
```

---

## API Design

### Chat Endpoint

```
POST /api/chat/message
Content-Type: application/json

{
    "message": "Should I sell my Apple stock?",
    "conversation_id": "conv_123",
    "include_agents": ["portfolio", "market_research", "risk_manager"]  // optional
}

Response:
{
    "response": "Based on analysis...",
    "analysis": {
        "portfolio": {...},
        "market_research": {...},
        "risk_manager": {...}
    },
    "conversation_id": "conv_123"
}
```

### Agent Debug Endpoint (Development)

```
GET /api/debug/agents/{agent_name}
GET /api/debug/chat/{conversation_id}/history
```

---

## Configuration & Environment

```env
# Claude API
CLAUDE_API_KEY=sk-...
CLAUDE_MODEL=claude-opus-4-1  # or latest

# eToro
ETORO_API_KEY=...
ETORO_API_SECRET=...

# Other brokers
SCALABLE_CAPITAL_API_KEY=...
BINANCE_API_KEY=...

# Data sources
FRED_API_KEY=...
NEWS_API_KEY=...

# Database
DATABASE_URL=postgresql://...

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

---

## Testing Strategy

### Unit Tests
- Each agent independently
- Context builder formatting
- Claude prompt templates

### Integration Tests
- Agent router decision logic
- Multi-agent execution
- Database queries with agents

### End-to-End Tests
- Full chat flow
- Real API calls (with fixtures)
- Error scenarios

### Manual Testing
- Chat interface
- Different question types
- Edge cases (user doesn't own stock, bad data, etc)

---

## Deployment Considerations

1. **Rate Limiting** - External API calls per agent
2. **Caching** - Agent results cache for similar questions
3. **Monitoring** - Track agent performance, Claude costs
4. **Scaling** - Async workers for agent execution
5. **Security** - API key rotation, input validation

---

## Success Metrics

- ✅ User can ask portfolio questions → get accurate analysis
- ✅ System handles questions about stocks user doesn't own
- ✅ Real-time price data from eToro
- ✅ Response time < 5 seconds
- ✅ Claude API cost < $X per month
- ✅ Chat history persists

---

## Open Questions / Decisions Needed

1. **Chat UI Framework** - React, Vue, or web component?
2. **Database Caching** - How long to cache agent results?
3. **Agent Parallelism** - Always run all agents or route smartly?
4. **eToro Auth** - OAuth or API key in environment?
5. **Fallback Data** - If API fails, use cached data or error?
6. **User Model** - Multiple users or single user for now?

---

## Next Steps

1. **Immediate (This Week)**
   - [ ] Review this design with team
   - [ ] Setup agent framework skeleton
   - [ ] Research eToro API details
   - [ ] Setup Claude API client

2. **Short Term (Next 2 Weeks)**
   - [ ] Implement Portfolio Agent
   - [ ] Integrate Claude
   - [ ] Build simple chat UI

3. **Medium Term (Weeks 3-4)**
   - [ ] eToro integration
   - [ ] Market Research Agent
   - [ ] Deploy MVP

