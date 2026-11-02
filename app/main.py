"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import router as portfolio_router, macro_router, exchange_rates_router
from app.database import get_session_factory
from app.scheduler import init_scheduler, start_scheduler, stop_scheduler
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="AI-powered investment desk for portfolio management",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(portfolio_router)
app.include_router(macro_router)
app.include_router(exchange_rates_router)


@app.on_event("startup")
async def startup_event():
    """Initialize scheduled data ingestion on app startup."""
    try:
        init_scheduler(get_session_factory, settings.fred_api_key or None)
        start_scheduler()
        logger.info("Data ingestion scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop scheduler on app shutdown"""
    stop_scheduler()


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "status": "running",
        "version": "0.1.0"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
