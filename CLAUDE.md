# AI Investment Desk - Development Guide

## Project Overview

Personal AI Investment Desk is an AI-powered investment management platform that consolidates portfolios across multiple brokers (Scalable Capital, Binance) and provides portfolio tracking, market intelligence, and automated trading capabilities.

## Architecture

### Backend (Python/FastAPI)
- **Database**: PostgreSQL for portfolio history, transactions, market data
- **API**: FastAPI with async support
- **Services**: Business logic layer for portfolio operations
- **Brokers**: Abstract interface + implementations for each broker
- **Models**: SQLAlchemy ORM for all entities
- **Agent Orchestration**: LangChain agent pattern with portfolio & research subagents

### Key Modules
- `app/models.py` - Database schema (Asset, Holding, Transaction, Price, etc.)
- `app/schemas.py` - Pydantic request/response models
- `app/services.py` - Portfolio business logic (legacy) + data sources (NewsAPI, SEC, etc.)
- `app/brokers/__init__.py` - Broker integration interface and VirtualBroker
- `app/routes.py` - API endpoints + agent initialization + chat endpoint
- `app/main.py` - FastAPI app setup
- `app/agents/` - Agent implementations:
  - `main_agent.py` - Main orchestrator (LangChain agent with subagents)
  - `portfolio_subagent.py` - Portfolio holdings/transactions queries
  - `research_subagent.py` - Valuation metrics (yfinance) + news (NewsAPI) with LLM-based tool routing
- `app/mcp/` - MCP (Model Context Protocol) tools for portfolio data access
- `app/llm/` - LLM integrations (Claude, Gemini, context building)

## Development Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 14+

### Local Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env

# Set up PostgreSQL database
createdb ai_investment_desk

# Run migrations (when added)
alembic upgrade head

# Start server
python run.py
```

## Development Workflow

### Phase 1: Portfolio Consolidation ✅ COMPLETE
- [x] Database schema and models
- [x] Virtual broker for testing
- [x] Portfolio service with CRUD operations
- [x] API endpoints for portfolio management
- [x] Source-attributed findings architecture
- [x] Market Research Agent with live news (NewsAPI)
- [ ] Real broker integrations (Scalable Capital, Binance)

### Phase 2: Multi-Agent Research System (CURRENT)
- [x] Set up LangChain infrastructure with subagents
- [x] Build Main Agent (orchestrator with portfolio & research subagents)
- [x] Build Portfolio Subagent (holdings, transactions, portfolio summary)
- [x] Build Research Subagent (Tier 1 + News integration)
  - [x] P/E ratio, EPS, market cap queries (via yfinance)
  - [x] Dividend yield queries
  - [x] 52-week high/low queries
  - [x] Company news fetching (via NewsAPI)
  - [x] LLM-based tool routing (infer nothing - only call what user asks for)
  - [ ] Tier 2: SEC filing analysis
  - [ ] Tier 3: Earnings transcript analysis
- [ ] Add more specialized subagents (market scanning, risk analysis, etc.)
- [ ] Implement RAG for SEC filing search (Tier 2/3 - future)
- [ ] Implement earnings transcript analysis (Tier 3 - future)
- [ ] Enhanced findings display in frontend

### Phase 3: AI Assistant
- LLM integration with agents
- Portfolio analysis with source attribution
- Evidence-grounded decision support (read-only; no trade execution)

### Phase 4: Trading Automation
- Strategy backtesting
- Paper trading
- Live trading with risk controls

## API Endpoints (Phase 1)

```
GET    /api/portfolio/summary              # Portfolio overview
GET    /api/portfolio/holdings              # All holdings
GET    /api/portfolio/holdings/{broker}     # Holdings by broker
POST   /api/portfolio/sync/virtual          # Load virtual broker data
GET    /api/portfolio/transactions          # Transaction history
POST   /api/portfolio/transactions          # Add manual transaction
POST   /api/portfolio/snapshot              # Create daily snapshot
```

## Testing

### With Virtual Broker
1. Start the server: `python run.py`
2. POST to `/api/portfolio/sync/virtual` to load sample data
3. GET `/api/portfolio/summary` to see portfolio overview
4. GET `/api/portfolio/holdings` to view all holdings

### Database Inspection
```bash
psql ai_investment_desk
\dt                    # List tables
SELECT * FROM holdings; # View holdings
```

## Code Style
- Use type hints throughout
- Decimal for financial values (never float)
- Async/await for broker APIs
- Services handle business logic, routes handle HTTP
- Models are thin - logic lives in services
- Agents are modular and composable

## Agent Architecture

### Multi-Agent System with LangChain

**Main Agent Pattern:**
Main agent calls Portfolio and Research subagents as tools, then synthesizes findings.

**Current Subagent Types:**
1. **Portfolio Subagent** - Tracks holdings, transactions, portfolio summary
2. **Research Subagent** - Company analysis with intelligent tool routing:
   - **Tier 1** (IMPLEMENTED): Valuation metrics (P/E, EPS, dividend, market cap, 52-week high/low) via yfinance
   - **News Integration** (IMPLEMENTED): Real-time headlines via NewsAPI
   - **Tool Routing**: LLM-based decisions - only calls tools user explicitly asks for
   - **Tier 2** (FUTURE): SEC filing analysis
   - **Tier 3** (FUTURE): Earnings transcript analysis

**Implementation Details:**
- Uses **LangChain** `create_agent()` with subagents wrapped as tools
- **yfinance** for valuation metrics (P/E, EPS, market cap, dividend, 52-week range)
- **NewsAPI** for real-time company news
- **Tool Routing Pattern**: Research subagent uses explicit LLM-based routing to call tools only when explicitly asked
- **Future**: RAG over SEC filings (10-K, 10-Q, 8-K) for Tier 2/3 research

### Agent Findings & Sources
- Every finding includes source attribution (Finding + SourceRef dataclasses)
- Credibility scores (0-1) based on source type (SEC=1.0, news=0.7, yfinance=0.9, etc.)
- Evidence levels: primary, secondary, derived
- URLs and metadata preserved for traceability

## Key Design Decisions

1. **Virtual Broker First**: Allows testing without real credentials
2. **Decimal for Money**: Precision matters in finance
3. **Service Layer**: Separates business logic from HTTP layer
4. **Abstract Broker Interface**: Easy to add new integrations
5. **Historical Snapshots**: Enables portfolio tracking over time
6. **LangChain Subagent Pattern**: Main agent orchestrates portfolio & research subagents as tools
7. **Source Attribution**: Every finding is verifiable with source, credibility, and URL
8. **LLM-Based Tool Routing**: Research tools are called only when explicitly requested (no inference)

## Environment Variables

See `.env.example` for required configuration:
- `DATABASE_URL` - PostgreSQL connection string
- `SCALABLE_CAPITAL_API_KEY/SECRET` - Broker credentials
- `BINANCE_API_KEY/SECRET` - Broker credentials
- `NEWSAPI_KEY` - NewsAPI for live news fetching
- `FRED_API_KEY` - Federal Reserve economic data
- `GEMINI_API_KEY` / `GEMINI_MODEL` - Google Gemini LLM
- `CLAUDE_API_KEY` / `CLAUDE_MODEL` - Anthropic Claude API
- `LLM_PROVIDER` - Which LLM to use (gemini, claude, ollama)
- `DEBUG` - Development mode flag

## Technologies & Libraries

### Core Stack
- **FastAPI** - REST API framework
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Primary database
- **Pydantic** - Data validation and serialization

### AI & Agents
- **LangChain** - Subagent orchestration with tool wrapping
- **Anthropic Claude** - LLM for agent reasoning and synthesis
- **Google Gemini** - Alternative LLM option
- **Ollama** - Local LLM option for development

### Data Sources
- **yfinance** - Stock pricing and fundamentals
- **NewsAPI** - Live financial news
- **SEC Edgar API** - SEC filings (10-K, 10-Q, 8-K)
- **FRED API** - Federal Reserve economic indicators
- **Seeking Alpha** - Earnings transcripts (optional)

### Vector Search & RAG (Future)
- **ChromaDB** - Vector database for SEC filings
- **sentence-transformers** - Embeddings for documents
- **PyPDF** - PDF parsing from SEC Edgar
- **BeautifulSoup4** - HTML parsing

## Development Priorities

### Immediate (Tier 1 - Quick Wins)
1. ✅ Research Subagent - Tier 1 (valuation queries + news)
2. ✅ Portfolio Subagent (holdings, transactions)
3. ✅ Main Agent orchestration with LangChain
4. Test with real user queries and validate tool routing

### Medium-term (Tier 2 - Enhanced Research)
1. Add more specialized subagents (risk analysis, sector analysis)
2. Build regulatory/lawsuit tracking
3. Implement sentiment analysis
4. Add analyst consensus integration

### Long-term (Tier 3 - Deep Analysis)
1. Implement SEC filing RAG
2. Add earnings transcript analysis
3. Implement financial red-flag detection
4. Build discovery agent (market scanning)

## Agent Development Guidelines

### Creating a New Agent
1. Create `app/agents/{agent_name}_agent.py`
2. Extend `BaseAgent` class with `name` parameter
3. Implement `async def execute(context: AgentContext) -> AgentOutput`
4. Use `Finding` + `SourceRef` for source-attributed results
5. Register in `app/routes.py` agents dictionary (passed to AssistantWorkflow)

### Main Agent (LangChain Subagent Pattern) Usage
```python
from app.agents.main_agent import create_main_agent

# Create main agent with portfolio & research subagents
llm_model = get_llm_model()
agent = create_main_agent(llm_model)

# Run agent
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "What is Microsoft's P/E ratio?"}]}
)

response = result.get("messages", [])[-1].content  # Final answer
```

### Research Subagent Tool Routing Pattern
Research subagent uses explicit LLM-based routing to prevent unnecessary tool calls:
```python
system_prompt = (
    "### Tool Usage & Routing\n"
    "1. **Fundamental Data:** Call `get_valuation_metrics` ONLY when explicitly asked about "
    "valuation ratios (P/E, EV/EBITDA, P/S), market cap, revenue, profitability, or balance sheet.\n"
    "2. **Recent Events:** Call `get_company_news` when asked about recent developments, "
    "earnings announcements, leadership changes, M&A, or market sentiment.\n"
    "3. **Comprehensive Queries:** If explicitly asked for 'full analysis', call BOTH tools. "
    "Otherwise, infer nothing - only call tools the user mentions.\n"
)
```
This ensures the agent calls tools **only when explicitly asked**, not based on inference.

### Finding Source Attribution Pattern
```python
finding = Finding(
    claim="The specific finding",
    source=SourceRef(
        source_type=SourceType.PRICE_DATA,
        source_name="Yahoo Finance",
        url="https://finance.yahoo.com/quote/MSFT",
        credibility_score=0.9,
        fetched_at=datetime.utcnow()
    ),
    evidence_level=EvidenceLevel.PRIMARY,
    confidence_score=0.9,
    timestamp=datetime.utcnow(),
    metadata={...}
)
```

## Testing & Development

### Test Main Agent with Sample Queries
Use `scripts/test_chat_prompts.py` to test the agent system:
```bash
# Run default test prompts
python scripts/test_chat_prompts.py

# Run custom prompt
python scripts/test_chat_prompts.py --prompt "What are my holdings?"

# Run interactively
python scripts/test_chat_prompts.py --interactive

# Show tool calls and execution traces
python scripts/test_chat_prompts.py --trace
```

## Next Steps

### Completed ✅
1. ✅ Set up LangChain orchestration with subagents
2. ✅ Implement Portfolio Subagent
3. ✅ Implement Research Subagent (Tier 1 + News)
4. ✅ LLM-based tool routing (only call what user asks)
5. ✅ Source-attributed findings architecture
6. ✅ Code cleanup (removed 17 redundant docs, all LangGraph files)

### Immediate (Tier 1 - Validation & Bugs)
1. Test with real user queries to validate tool routing
2. Fix any edge cases in portfolio/research queries
3. Enhance error handling

### Medium-term (Tier 2 - Enhanced Research)
1. Add more specialized subagents (risk analysis, sector analysis)
2. Implement SEC filing analysis
3. Add earnings announcement integration
4. Implement sentiment analysis from news

### Long-term (Tier 3 - Deep Analysis)
1. Implement SEC filing RAG with ChromaDB
2. Add earnings transcript analysis
3. Build discovery agent (market scanning)
4. Add risk assessment agent

## Troubleshooting

**Database connection fails**: Check DATABASE_URL and PostgreSQL is running
```bash
psql -U user -h localhost -d ai_investment_desk
```

**Import errors**: Ensure virtual environment is activated and dependencies installed
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**LangGraph issues**: Ensure langgraph and langchain are installed
```bash
pip install langgraph langchain langchain-community
```
