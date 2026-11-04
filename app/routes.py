"""
API routes for portfolio management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import date, datetime
import uuid
import logging

from app.database import get_db, get_session_factory
from app.models import BrokerType, AssetType, TransactionType
from app.schemas import (
    HoldingResponse, PortfolioSummary, TransactionResponse,
    TransactionCreate,
)
from app.chat_schemas import ChatMessage, ChatResponse
from app.services import PortfolioService, MacroDataService, SECFundamentalsService
from app.services import EtoroPriceService, ExchangeRateService, NewsService
from app.brokers import VirtualBroker
from app.config import settings
from app.agents import (
    AgentContext,
    AgentRouter,
    MacroContextAgent,
    MarketResearchAgent,
    RiskManagerAgent,
    SynthesisAgent,
    ValuationAgent,
    execute_agents_parallel,
)
from app.agents.portfolio_agent import PortfolioAgent
from app.llm.client import LLMClient
from app.llm.context_builder import ContextBuilder
from app.llm.providers import LLMFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
macro_router = APIRouter(prefix="/api/macro", tags=["macro"])
exchange_rates_router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"])
news_router = APIRouter(prefix="/api/news", tags=["news"])
chat_router = APIRouter(prefix="/api/chat", tags=["chat"])
prices_router = APIRouter(prefix="/api/prices", tags=["prices"])
fundamentals_router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])

# Initialize brokers
virtual_broker = VirtualBroker()

# Initialize agents and router
agents = {
    "portfolio": PortfolioAgent(),
    "market_research": MarketResearchAgent(),
    "macro": MacroContextAgent(),
    "risk": RiskManagerAgent(),
    "valuation": ValuationAgent(),
}
agent_router = AgentRouter(agents)
synthesis_agent = SynthesisAgent()

# Initialize LLM client based on config
llm_client = None
if settings.llm_provider.lower() == "claude":
    if settings.claude_api_key:
        try:
            provider = LLMFactory.create_provider(
                provider_type="claude",
                api_key=settings.claude_api_key,
                model=settings.claude_model,
            )
            llm_client = LLMClient(provider)
            logger.info(f"LLM Provider: Claude ({settings.claude_model})")
        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
    else:
        logger.warning("Claude provider selected but CLAUDE_API_KEY not set")
elif settings.llm_provider.lower() == "gemini":
    if settings.gemini_api_key:
        try:
            provider = LLMFactory.create_provider(
                provider_type="gemini",
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            )
            llm_client = LLMClient(provider)
            logger.info("LLM Provider: Gemini (%s)", settings.gemini_model)
        except Exception as e:
            logger.error("Failed to initialize Gemini: %s", e)
    else:
        logger.warning("Gemini provider selected but GEMINI_API_KEY not set")
else:
    # Default to Ollama (free, local)
    try:
        provider = LLMFactory.create_provider(
            provider_type="ollama",
            api_url=settings.ollama_api_url,
            model=settings.ollama_model,
        )
        llm_client = LLMClient(provider)
        logger.info(f"LLM Provider: Ollama ({settings.ollama_model}) at {settings.ollama_api_url}")
    except Exception as e:
        logger.error(f"Failed to initialize Ollama: {e}")


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(get_db)):
    """Get overall portfolio summary"""
    return PortfolioService.get_portfolio_summary(db)


@router.get("/holdings", response_model=List[HoldingResponse])
def get_all_holdings(db: Session = Depends(get_db)):
    """Get all holdings across all brokers"""
    return PortfolioService.get_all_holdings(db)


@router.get("/holdings/{broker}", response_model=List[HoldingResponse])
def get_broker_holdings(broker: BrokerType, db: Session = Depends(get_db)):
    """Get holdings for a specific broker"""
    return PortfolioService.get_holdings_by_broker(db, broker)


@router.post("/sync/virtual")
async def sync_virtual_broker(db: Session = Depends(get_db)):
    """
    Load portfolio from virtual broker (for testing).
    This will populate the database with sample holdings and transactions.
    """
    from app.models import Asset

    try:
        # Get holdings from virtual broker
        holdings = await virtual_broker.get_holdings()
        transactions = await virtual_broker.get_transactions()

        # Create assets from holdings
        for holding in holdings:
            PortfolioService.get_or_create_asset(
                db,
                symbol=holding.symbol,
                name=holding.symbol,
                asset_type=AssetType.STOCK,
            )

        # Load transactions
        for txn in transactions:
            asset = db.query(Asset).filter(Asset.symbol == txn.symbol).first()
            if not asset:
                asset = PortfolioService.get_or_create_asset(
                    db,
                    symbol=txn.symbol,
                    name=txn.symbol,
                    asset_type=AssetType.STOCK,
                )

            PortfolioService.add_transaction(
                db,
                asset_id=asset.id,
                broker=BrokerType.SCALABLE_CAPITAL,
                transaction_type=TransactionType(txn.transaction_type),
                quantity=txn.quantity,
                price=txn.price,
                total_amount=txn.quantity * txn.price,
                transaction_date=txn.timestamp,
                broker_transaction_id=txn.broker_id
            )

        # Update prices
        observed_at = datetime.utcnow()
        prices_dict = {
            h.symbol: (
                h.current_price,
                observed_at,
                "virtual_broker",
                h.currency,
            )
            for h in holdings
        }
        PortfolioService.update_market_prices(db, prices_dict)

        return {
            "status": "synced",
            "holdings_loaded": len(holdings),
            "transactions_loaded": len(transactions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get transaction history"""
    from app.models import Transaction

    transactions = db.query(Transaction).offset(skip).limit(limit).all()
    return transactions


@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """Manually add a transaction"""
    txn = PortfolioService.add_transaction(
        db,
        asset_id=transaction.asset_id,
        broker=transaction.broker,
        transaction_type=transaction.transaction_type,
        quantity=transaction.quantity,
        price=transaction.price,
        total_amount=transaction.total_amount,
        commission=transaction.commission,
        transaction_date=transaction.transaction_date
    )
    return txn


@router.post("/snapshot")
def create_portfolio_snapshot(db: Session = Depends(get_db)):
    """Create a portfolio snapshot"""
    snapshot = PortfolioService.create_snapshot(db)
    return {
        "snapshot_id": snapshot.id,
        "snapshot_date": snapshot.snapshot_date,
        "total_value": snapshot.total_value
    }


@router.post("/sync/{broker}")
def sync_broker_portfolio(broker: BrokerType, db: Session = Depends(get_db)):
    """
    Sync portfolio from broker.
    TODO: Replace with real broker integrations.
    """
    if broker == BrokerType.SCALABLE_CAPITAL:
        raise HTTPException(
            status_code=501,
            detail="Scalable Capital integration coming soon"
        )
    elif broker == BrokerType.BINANCE:
        raise HTTPException(
            status_code=501,
            detail="Binance integration coming soon"
        )

    return {"status": "integration_pending"}


# Macro data endpoints
@macro_router.get("/latest", response_model=Dict)
def get_latest_macro(db: Session = Depends(get_db)):
    """Get latest values for all macro indicators"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.get_latest_macro_data()


@macro_router.get("/series/{series_id}")
def get_macro_series(series_id: str, days: int = 30, db: Session = Depends(get_db)):
    """Get historical data for a macro series"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.get_macro_series(series_id, days)


@macro_router.post("/jobs/daily")
def run_daily_macro_job(start_date: date | None = None, db: Session = Depends(get_db)):
    """Manually trigger daily macro data fetch (VIX, DFF, DGS10)"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.fetch_and_store_daily_macro(
        start_date.isoformat() if start_date else None
    )


@macro_router.post("/jobs/monthly")
def run_monthly_macro_job(start_date: date | None = None, db: Session = Depends(get_db)):
    """Manually trigger monthly macro data fetch (CPI)"""
    if not settings.fred_api_key:
        raise HTTPException(status_code=400, detail="FRED_API_KEY not configured")
    service = MacroDataService(db, settings.fred_api_key)
    return service.fetch_and_store_monthly_macro(
        start_date.isoformat() if start_date else None
    )


@exchange_rates_router.get("/latest")
def get_latest_exchange_rates(db: Session = Depends(get_db)):
    """Get latest stored EUR exchange rates."""
    return ExchangeRateService(db).get_latest_rates()


@fundamentals_router.post("/sync/sec")
async def sync_sec_company_facts(db: Session = Depends(get_db)) -> Dict:
    """Fetch the latest supported SEC company facts for held stocks and ETFs."""
    if not settings.sec_user_agent or "@" not in settings.sec_user_agent:
        raise HTTPException(
            status_code=503,
            detail=(
                "Set SEC_USER_AGENT to an application name and contact email, "
                "for example 'AI Investment Desk contact: you@example.com'."
            ),
        )
    result = await SECFundamentalsService(
        db, settings.sec_user_agent
    ).sync_portfolio_facts()
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result["message"])
    return result


@exchange_rates_router.get("/history/{base_currency}/{quote_currency}")
def get_exchange_rate_history(
    base_currency: str,
    quote_currency: str,
    limit: int = 1095,
    db: Session = Depends(get_db),
):
    """Get stored daily observations for a currency pair."""
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
    return ExchangeRateService(db).get_rate_history(base_currency, quote_currency, limit)


@exchange_rates_router.post("/sync")
def sync_exchange_rates(start_date: date | None = None, db: Session = Depends(get_db)):
    """Fetch daily exchange rates; optionally backfill from a start date."""
    result = ExchangeRateService(db).fetch_and_store_daily_rates(
        start_date.isoformat() if start_date else None
    )
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result["message"])
    return result


# News endpoints
@news_router.get("/portfolio")
def get_portfolio_news(days: int = 7, limit: int = 50, db: Session = Depends(get_db)) -> Dict:
    """Get news for all stocks in current portfolio"""
    return NewsService.get_portfolio_news(db, days=days, limit=limit)


@news_router.get("/{symbol}")
def get_symbol_news(
    symbol: str,
    days: int = 30,
    limit: int = 20,
    db: Session = Depends(get_db)
) -> List[Dict]:
    """Get news for specific stock symbol"""
    return NewsService.get_symbol_news(db, symbol, days=days, limit=limit)


@news_router.get("/{symbol}/latest")
def get_latest_symbol_news(
    symbol: str,
    limit: int = 5,
    db: Session = Depends(get_db)
) -> List[Dict]:
    """Get latest N articles for a symbol"""
    return NewsService.get_latest_news(db, symbol, limit=limit)


@news_router.post("/fetch-portfolio")
async def manually_fetch_portfolio_news(db: Session = Depends(get_db)) -> Dict:
    """Manually trigger news fetch for all portfolio stocks"""
    result = await NewsService.fetch_and_store_portfolio_news(db, days=7)
    if result["status"] != "success":
        raise HTTPException(status_code=500, detail=result.get("message", "Failed to fetch news"))
    return result


@news_router.get("/stats/summary")
def get_news_stats(db: Session = Depends(get_db)) -> Dict:
    """Get statistics about stored news"""
    return NewsService.get_news_stats(db)


@prices_router.post("/sync/etoro")
async def sync_etoro_prices(db: Session = Depends(get_db)) -> Dict:
    """Fetch current eToro prices for held stocks, ETFs, and crypto in USD."""
    if not settings.etoro_api_key or not settings.etoro_user_key:
        raise HTTPException(
            status_code=503,
            detail="Configure ETORO_API_KEY and ETORO_USER_KEY to fetch prices",
        )
    result = await EtoroPriceService(db).sync_portfolio_prices()
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result)
    return result


@prices_router.get("/latest")
def get_latest_etoro_prices(db: Session = Depends(get_db)) -> List[Dict]:
    """Get the latest stored eToro price for each tracked stock, ETF, and crypto."""
    return EtoroPriceService.get_latest_portfolio_prices(db)


# Chat endpoint
@chat_router.post("/message", response_model=ChatResponse)
async def chat_message(chat_msg: ChatMessage):
    """
    Main chat endpoint for portfolio analysis.

    1. Route message to appropriate agents
    2. Execute agents in parallel
    3. Aggregate results
    4. Send to LLM for analysis
    5. Return response
    """
    if not llm_client:
        raise HTTPException(
            status_code=500,
            detail="LLM not configured. Setup Ollama locally or set CLAUDE_API_KEY."
        )

    try:
        # Generate conversation ID if not provided
        conversation_id = chat_msg.conversation_id or str(uuid.uuid4())

        logger.info(f"Processing chat message: {chat_msg.message[:100]}... (conv: {conversation_id})")

        # Decide which agents to run
        agents_to_run = agent_router.decide_agents(chat_msg.message)

        if chat_msg.include_agents is not None:
            unknown_agents = sorted(
                set(chat_msg.include_agents) - set(agent_router.list_agents())
            )
            if unknown_agents:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown agents: {', '.join(unknown_agents)}",
                )
            agents_to_run = [
                agent_router.agents[name]
                for name in chat_msg.include_agents
            ]

        if not agents_to_run:
            raise HTTPException(
                status_code=400,
                detail="No agents could handle this message"
            )

        logger.info(f"Running agents: {[a.name for a in agents_to_run]}")

        # Create context for agents
        context = AgentContext(
            user_message=chat_msg.message,
            metadata={
                "db_factory": get_session_factory(),
                "llm_client": llm_client,
            },
        )

        # Execute agents in parallel
        agent_outputs = await execute_agents_parallel(agents_to_run, context)

        # Build context from agent outputs
        context_dict = ContextBuilder.build_context(agent_outputs)

        logger.info(f"Agent execution complete. Agents used: {[a.agent_name for a in agent_outputs]}")

        synthesis_output = await synthesis_agent.execute(
            AgentContext(
                user_message=chat_msg.message,
                metadata={
                    "agent_outputs": context_dict,
                    "llm_client": llm_client,
                },
            )
        )
        if not synthesis_output.success:
            raise HTTPException(
                status_code=502,
                detail=f"Final response synthesis failed: {synthesis_output.error}",
            )
        context_dict["synthesis"] = synthesis_output.data

        logger.info(f"LLM response received for conversation {conversation_id}")

        # Return response
        return ChatResponse(
            response=synthesis_output.data["response"],
            conversation_id=conversation_id,
            analysis=context_dict,
            timestamp=datetime.utcnow(),
            agents_used=[
                *[output.agent_name for output in agent_outputs],
                synthesis_output.agent_name,
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing failed: {str(e)}"
        )
