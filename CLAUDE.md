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
- **Agent Orchestration**: LangGraph for multi-agent workflows + LangChain for RAG/document processing

### Key Modules
- `app/models.py` - Database schema (Asset, Holding, Transaction, Price, etc.)
- `app/schemas.py` - Pydantic request/response models
- `app/services.py` - Portfolio business logic
- `app/brokers/__init__.py` - Broker integration interface and VirtualBroker
- `app/routes.py` - API endpoints + agent orchestration
- `app/main.py` - FastAPI app setup
- `app/agents/` - Individual agent implementations (Portfolio, Research, Discovery)
- `app/orchestrator/` - LangGraph workflow definitions and orchestration logic
- `app/llm/` - LLM integrations (Claude, context building, prompts)

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
- [x] Set up LangGraph + LangChain infrastructure
- [x] Build LangGraph Orchestrator (LLM-based routing, no keyword matching)
- [x] Build Research Agent (Tier 1: Valuation lookups)
  - [x] P/E ratio, EPS, market cap queries
  - [x] Dividend yield queries
  - [x] 52-week high/low queries
  - [ ] Tier 2: News & events integration
  - [ ] Tier 3: SEC filing RAG search
- [ ] Build Discovery Agent (market scanning)
- [ ] Build News Agent (real-time headlines & sentiment)
- [ ] Implement RAG for SEC filing search (Tier 3)
- [ ] Implement earnings transcript analysis (Tier 3)
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
- Use TypedDict for agent state in LangGraph

## Agent Architecture

### Multi-Agent System with LangGraph

**Orchestrator Flow:**
1. **Route** - LLM intelligently decides which agents to run (no keyword matching)
2. **Execute** - Selected agents run in parallel
3. **Synthesize** - LLM combines findings into final answer

**Agent Types:**
1. **Portfolio Agent** - Tracks holdings, gains/losses, sector exposure
2. **Research Agent** (Tier 1, 2, 3) - Company analysis:
   - **Tier 1**: Valuation metrics (P/E, EPS, dividend, market cap, 52-week high/low)
   - **Tier 2**: News, events, regulatory announcements
   - **Tier 3**: SEC filing RAG search, earnings transcript analysis
3. **News Agent** - Real-time headlines and market sentiment
4. **Discovery Agent** - Market scanning for investment ideas
5. **Synthesizer Agent** - Combines findings via LLM

**Orchestration Architecture:**
```
User Query
    ↓
Orchestrator.route() → LLM decides agents (no keyword matching)
    ↓
Orchestrator.execute() → Run selected agents in parallel
    ↓
Orchestrator.synthesize() → LLM combines findings
    ↓
Final Answer with Source Attribution
```

- Uses **LangGraph** for state management and workflow
- Agents run concurrently via `execute_agents_parallel()`
- **LangChain** for:
  - RAG over SEC filings (10-K, 10-Q, 8-K) - Tier 3
  - Document processing and chunking
  - Vector search and semantic retrieval
  - LLM prompt management

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
6. **LangGraph + LangChain**: Multi-agent orchestration with RAG capabilities
7. **Source Attribution**: Every finding is verifiable with source, credibility, and URL
8. **Parallel Agent Execution**: Agents run concurrently, results synthesized by LLM

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
- **LangGraph** - Multi-agent orchestration and workflow management
- **LangChain** - Document processing, RAG, prompt management
- **Anthropic Claude** - LLM for synthesis and analysis
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
1. Build Research Agent - Tier 1 (valuation queries)
   - P/E ratio, market cap, EPS, dividend, 52-week high/low
   - Uses yfinance (already integrated)
   - No new dependencies needed
2. Build Discovery Agent (market scanning)
3. Set up LangGraph orchestrator
4. Test parallel agent execution

### Medium-term (Tier 2 - Enhanced Research)
1. Add news & event synthesis to Research Agent
2. Build regulatory/lawsuit tracking
3. Implement sentiment analysis
4. Add analyst consensus integration

### Long-term (Tier 3 - Deep Analysis)
1. Implement SEC filing RAG
2. Add earnings transcript analysis
3. Implement financial red-flag detection
4. Build sector/industry analysis agent

## Agent Development Guidelines

### Creating a New Agent
1. Create `app/agents/{agent_name}_agent.py`
2. Extend `BaseAgent` class
3. Implement `async def execute(context: AgentContext) -> AgentOutput`
4. Use `Finding` + `SourceRef` for source-attributed results
5. Register in `app/orchestrator/orchestrator.py` (not routes.py)

### Orchestrator Usage
```python
from app.orchestrator import Orchestrator

# Initialize with agents
orchestrator = Orchestrator({
    "portfolio": PortfolioAgent(),
    "research": ResearchAgent(),
    "news": NewsAgent(),
    "discovery": DiscoveryAgent(),
})

# Run orchestrator
state = await orchestrator.ainvoke(
    user_query="What is Microsoft's P/E ratio?",
    llm_client=llm_client,
    db_factory=get_session_factory(),
    mcp_client=mcp_client,
)

response = state["response"]  # Final answer with sources
```

### LangGraph Workflow Pattern
```
START
  ↓
_route (LLM: which agents?)
  ↓
_execute (Run agents in parallel)
  ↓
_synthesize (LLM: combine findings)
  ↓
END
```

**Key: No keyword matching** - LLM intelligently decides based on user intent, not hardcoded rules.

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

## Next Steps

1. ✅ Update CLAUDE.md with LangGraph + LangChain architecture
2. Install additional dependencies for Tier 2 & 3:
   ```bash
   pip install sec-edgar chromadb sentence-transformers pypdf beautifulsoup4 langchain langchain-community
   ```
3. Build Research Agent - Tier 1 (valuation queries)
4. Build Discovery Agent
5. Create LangGraph orchestrator workflow
6. Test parallel agent execution
7. Enhance Research Agent with Tier 2 (news/regulatory)
8. Implement RAG for Tier 3 (SEC filings)

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
