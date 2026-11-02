# AI Investment Desk - Implementation Roadmap

## Completed (Phase 1a - Foundation)

### ✅ Agent Framework
- BaseAgent abstract class with async execute pattern
- AgentContext and AgentOutput data models
- AgentRouter for intelligent agent selection based on keywords
- Parallel execution system with timing and error handling
- Located in: `app/agents/`

### ✅ Claude LLM Integration
- ClaudeClient wrapper for Anthropic API
- System prompts for different analysis contexts
- ContextBuilder to aggregate and format agent outputs
- Located in: `app/llm/`

### ✅ Portfolio Agent
- Queries database for holdings, transactions, portfolio summary
- Returns structured data for Claude analysis
- Handles relationships (asset, broker, quantities)
- Located in: `app/agents/portfolio_agent.py`

### ✅ Chat Endpoint
- `POST /api/chat/message` endpoint
- Routes user questions to appropriate agents
- Parallel execution and aggregation
- Claude synthesis and response
- Returns full analysis context
- Located in: `app/routes.py`

### ✅ Configuration
- Added CLAUDE_API_KEY to settings
- Added claude_model to config
- Anthropic package in requirements.txt

---

## In Progress / Pending (Phase 1b - Complete MVP)

### Task #5: eToro Integration (HIGH PRIORITY)
**Status**: Not started
**Objective**: Fetch real-time prices and holdings from eToro API

**What needs to be done:**

1. **Research eToro API**
   - [ ] Document API endpoints available
   - [ ] Understand authentication (OAuth vs API key)
   - [ ] Check rate limits and quotas
   - [ ] Review market data available (stocks, crypto, ETFs)
   - [ ] Identify news/sentiment endpoints

2. **Build eToro Client** (`app/brokers/etoro/`)
   - [ ] Create `__init__.py`
   - [ ] Create `client.py` with eToroBroker class
   - [ ] Implement `async get_prices(symbols: List[str]) -> Dict`
   - [ ] Implement `async get_holdings() -> List[Holding]`
   - [ ] Implement `async get_news(symbol: str) -> List[NewsArticle]`
   - [ ] Implement `async get_fundamentals(symbol: str) -> Dict`
   - [ ] Add authentication (API key management)
   - [ ] Add error handling and retry logic

3. **Integration Points**
   - [ ] Add eToro client initialization to routes.py
   - [ ] Update Price model if needed for real-time data
   - [ ] Add eToro to BrokerType enum if not already there

4. **Testing**
   - [ ] Test with demo account credentials
   - [ ] Mock API responses for CI/testing
   - [ ] Verify price feed accuracy

**Files to create:**
- `app/brokers/etoro/__init__.py`
- `app/brokers/etoro/client.py`

**Files to modify:**
- `app/models.py` (if needed)
- `app/routes.py` (initialize eToro client)

---

### Task #6: Market Research Agent (HIGH PRIORITY)
**Status**: Not started
**Objective**: Fetch and analyze news, sentiment, analyst ratings

**What needs to be done:**

1. **Build Market Research Agent** (`app/agents/market_research_agent.py`)
   - [ ] Create class inheriting from BaseAgent
   - [ ] Implement news fetching for portfolio holdings
   - [ ] Implement sentiment analysis (if available via API)
   - [ ] Implement analyst rating aggregation
   - [ ] Format output for Claude

2. **Data Sources**
   - [ ] Use existing NewsService for news
   - [ ] Add analyst rating API (e.g., Alpha Vantage, IEX Cloud)
   - [ ] Consider SEC Edgar for filings
   - [ ] Format as readable summaries

3. **Integration**
   - [ ] Register in agent_router in routes.py
   - [ ] Update keyword routing logic if needed
   - [ ] Test with sample portfolio

**Example Implementation Pattern:**
```python
class MarketResearchAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentOutput:
        # Get symbols from context or portfolio
        # Fetch news for each symbol
        # Get analyst ratings
        # Return formatted data
```

**Files to create:**
- `app/agents/market_research_agent.py`

**Files to modify:**
- `app/routes.py` (register agent)

---

### Task #7: Frontend Chat Interface (HIGH PRIORITY)
**Status**: Not started
**Objective**: Build web UI for chat interaction

**What needs to be done:**

1. **Project Setup**
   - [ ] Choose framework (React recommended)
   - [ ] Setup TypeScript configuration
   - [ ] Install dependencies (React, UI library, HTTP client)
   - [ ] Setup build configuration

2. **Chat Components**
   - [ ] ChatWindow component (main container)
   - [ ] MessageList component (display messages)
   - [ ] InputBox component (user input)
   - [ ] Message component (individual message display)
   - [ ] LoadingIndicator component (while awaiting response)

3. **Portfolio Context UI**
   - [ ] PortfolioSummary widget
   - [ ] Holdings list view
   - [ ] Recent transactions view
   - [ ] Summary metrics (total value, gain/loss, %)

4. **Pages**
   - [ ] ChatPage (main chat interface)
   - [ ] DashboardPage (portfolio overview)
   - [ ] SettingsPage (API configuration)

5. **Services**
   - [ ] chatApi.ts (fetch wrapper for /api/chat/message)
   - [ ] Portfolio fetching (get holdings, summary)
   - [ ] Error handling and retry logic

6. **Styling**
   - [ ] Theme (light/dark mode)
   - [ ] Responsive design (mobile, tablet, desktop)
   - [ ] Accessibility (WCAG compliance)

7. **Features**
   - [ ] Conversation history persistence (localStorage or backend)
   - [ ] Message streaming/typing indicators
   - [ ] Error messages and user feedback
   - [ ] Copy-to-clipboard for responses
   - [ ] Clear conversation option

**Directory Structure:**
```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageList.tsx
│   │   ├── InputBox.tsx
│   │   ├── Message.tsx
│   │   ├── PortfolioSummary.tsx
│   │   └── LoadingIndicator.tsx
│   ├── pages/
│   │   ├── ChatPage.tsx
│   │   ├── DashboardPage.tsx
│   │   └── SettingsPage.tsx
│   ├── services/
│   │   ├── chatApi.ts
│   │   └── portfolioApi.ts
│   ├── styles/
│   │   └── App.css
│   ├── App.tsx
│   └── index.tsx
├── package.json
└── tsconfig.json
```

**API Calls Needed:**
- `POST /api/chat/message` - Send question
- `GET /api/portfolio/summary` - Get portfolio overview
- `GET /api/portfolio/holdings` - Get all holdings
- `GET /api/news` - Get recent portfolio news

---

## Phase 2 - Enhanced Analysis (Future)

### Task #8: Valuation Agent (MEDIUM PRIORITY)
- Build DCF valuation models
- Comparable company analysis
- Fair value estimates
- Upside/downside scenarios

**Depends on:** eToro integration for real prices

### Task #9: Risk Manager Agent (MEDIUM PRIORITY)
- Portfolio risk calculations
- Stress testing
- Diversification analysis
- Position concentration metrics

**Depends on:** Market Research Agent

### Task #10: Macro Context Agent (MEDIUM PRIORITY)
- Enhanced macro data analysis
- Correlation to portfolio
- Scenario modeling
- Market regime detection

**Depends on:** Existing MacroDataService (mostly done)

### Task #11: Real Broker Integrations (MEDIUM PRIORITY)
- Scalable Capital OAuth flow
- Binance API connection
- Holdings reconciliation
- Multi-broker sync

**Depends on:** eToro working first

---

## Phase 3 - Autonomous Trading (Future)

### Task #12: Trade Execution Framework
- Order placement logic
- Risk validation
- Trade approval workflow
- Paper trading first

**Depends on:** All Phase 2 agents working

### Task #13: Backtesting Engine
- Strategy replay
- Historical performance
- Monte Carlo simulations
- Parameter optimization

**Depends on:** Valuation + Risk agents

### Task #14: Agent Capital Allocation
- Data model for agent budgets
- Trade tracking per agent
- P&L calculation
- Performance metrics

**Depends on:** Trade execution working

---

## Known Limitations / Technical Debt

### Current Limitations
1. **Single User Only** - No multi-user support yet
2. **No Persistence** - Conversation history not saved
3. **Limited Data Sources** - No eToro real-time yet
4. **Basic Agent Routing** - Keyword-based, not NLP
5. **No Real Broker Access** - Virtual broker only
6. **SQLite Database** - Not production-ready

### Technical Debt to Address
1. Add proper logging configuration
2. Setup structured logging with correlation IDs
3. Add request/response validation
4. Setup integration tests with mocked APIs
5. Add API rate limiting
6. Setup caching strategy for agent results
7. Add database migrations for chat history
8. Setup monitoring and alerting
9. Add authentication/authorization framework
10. Implement database pooling for production

---

## Testing Strategy

### Unit Tests Needed
- [ ] Each agent independently (with mocked DB)
- [ ] ContextBuilder formatting
- [ ] Claude prompts (validate structure)
- [ ] API schema validation
- [ ] Router keyword matching

### Integration Tests Needed
- [ ] Full chat flow (agent → Claude → response)
- [ ] Database queries with transactions
- [ ] eToro API mocking
- [ ] Multi-agent parallel execution

### Manual Testing Checklist
- [ ] Chat with portfolio questions
- [ ] Chat with market analysis questions
- [ ] Error handling (bad inputs, API failures)
- [ ] Performance (response time < 5s)
- [ ] Edge cases (empty portfolio, no holdings, etc)

---

## Environment Configuration Needed

### Required Environment Variables
```
# Database
DATABASE_URL=postgresql://user:pass@localhost/ai_investment_desk

# Claude API
CLAUDE_API_KEY=sk-...
CLAUDE_MODEL=claude-opus-4-1

# eToro (when implemented)
ETORO_API_KEY=...
ETORO_API_SECRET=...

# Other data sources (already configured)
FRED_API_KEY=...
NEWSAPI_KEY=...
```

### Development Setup
```bash
# 1. Create .env file with above variables
# 2. Activate venv: source venv/bin/activate
# 3. Install deps: pip install -r requirements.txt
# 4. Setup DB: python init_db.py
# 5. Run server: python run.py
# 6. Test chat: curl -X POST http://localhost:8000/api/chat/message \
#    -H "Content-Type: application/json" \
#    -d '{"message": "What is my portfolio value?"}'
```

---

## Success Criteria for MVP (Phase 1)

- [x] Agent framework working
- [x] Chat endpoint receives questions
- [x] Portfolio agent queries database
- [x] Claude integration working
- [ ] eToro integration working
- [ ] Frontend UI working
- [ ] User can ask about portfolio and get AI response
- [ ] Response time < 5 seconds
- [ ] No crashes on edge cases
- [ ] Proper error messages to user

---

## Estimated Timeline

| Phase | Tasks | Est. Days |
|-------|-------|-----------|
| 1a (Done) | Agent framework, Claude, Portfolio Agent, Chat endpoint | ✅ Done |
| 1b (In Progress) | eToro, Market Research, Frontend | 10-14 days |
| 2 (Next) | Valuation, Risk, Macro, Real brokers | 14-21 days |
| 3 (Future) | Trading, Backtesting, Capital allocation | 21-28 days |

---

## Communication with User

**What they need to know:**
1. System architecture is solid - agent-based, extensible
2. Core foundation is complete - ready for enhancements
3. Next blocker is eToro integration for real data
4. Frontend is straightforward React build
5. Full MVP testable within 2 weeks

**What to ask before proceeding:**
1. Which task should we tackle first? (eToro, Market Research, or Frontend)
2. Any preference on frontend framework?
3. Should we setup basic frontend first to test the chat endpoint?
4. Do you have eToro API credentials for integration testing?

