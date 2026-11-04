import logging
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import asyncio

from app.brokers.etoro import EtoroMarketDataClient
from app.services import (
    EtoroPriceService,
    ExchangeRateService,
    MacroDataService,
    NewsService,
)

logger = logging.getLogger(__name__)

scheduler = None


def init_scheduler(
    session_factory: Callable,
    fred_api_key: Optional[str] = None,
    etoro_api_key: Optional[str] = None,
    etoro_user_key: Optional[str] = None,
):
    """Initialize daily FX, news, and optional macro and eToro price jobs."""
    global scheduler

    if scheduler is not None:
        return scheduler

    scheduler = BackgroundScheduler()
    fx_timezone = pytz.timezone("Europe/Berlin")
    scheduler.add_job(
        func=lambda: _run_exchange_rate_job(session_factory),
        trigger=CronTrigger(hour=17, minute=30, timezone=fx_timezone),
        id="daily_exchange_rates",
        name="Fetch daily EUR exchange rates",
        replace_existing=True,
    )

    if fred_api_key:
        macro_timezone = pytz.timezone("US/Eastern")
        scheduler.add_job(
            func=lambda: _run_macro_job(session_factory, fred_api_key, monthly=False),
            trigger=CronTrigger(hour=16, minute=35, timezone=macro_timezone),
            id="daily_macro",
            name="Fetch daily macro data (VIX, DFF, DGS10)",
            replace_existing=True,
        )
        scheduler.add_job(
            func=lambda: _run_macro_job(session_factory, fred_api_key, monthly=True),
            trigger=CronTrigger(hour=10, minute=0, timezone=macro_timezone),
            id="monthly_macro",
            name="Fetch monthly macro data (CPI)",
            replace_existing=True,
        )

    # News fetching job - run daily after market close (8 PM ET)
    news_timezone = pytz.timezone("US/Eastern")
    scheduler.add_job(
        func=lambda: _run_news_job(session_factory),
        trigger=CronTrigger(hour=20, minute=0, timezone=news_timezone),
        id="daily_portfolio_news",
        name="Fetch news for portfolio stocks",
        replace_existing=True,
    )

    if etoro_api_key and etoro_user_key:
        etoro_timezone = pytz.timezone("US/Eastern")
        scheduler.add_job(
            func=lambda: _run_etoro_price_job(
                session_factory, etoro_api_key, etoro_user_key
            ),
            trigger=CronTrigger(hour=20, minute=30, timezone=etoro_timezone),
            id="daily_etoro_prices",
            name="Fetch daily eToro portfolio prices in USD",
            replace_existing=True,
        )

    logger.info("APScheduler initialized for scheduled data ingestion")
    return scheduler


def _run_exchange_rate_job(session_factory: Callable) -> None:
    db = session_factory()
    try:
        result = ExchangeRateService(db).fetch_and_store_daily_rates()
        if result["status"] != "success":
            logger.error("Daily exchange-rate job failed: %s", result["message"])
    finally:
        db.close()


def _run_macro_job(session_factory: Callable, api_key: str, monthly: bool) -> None:
    db = session_factory()
    try:
        service = MacroDataService(db, api_key)
        result = (
            service.fetch_and_store_monthly_macro()
            if monthly
            else service.fetch_and_store_daily_macro()
        )
        if result["status"] != "success":
            logger.error("Scheduled macro job failed: %s", result["message"])
    finally:
        db.close()


def _run_news_job(session_factory: Callable) -> None:
    """Fetch news for all portfolio stocks"""
    db = session_factory()
    try:
        result = asyncio.run(NewsService.fetch_and_store_portfolio_news(db, days=7))
        if result["status"] != "success":
            logger.error("Daily news job failed: %s", result.get("message", "Unknown error"))
        else:
            logger.info(
                f"Daily news job complete: {result['articles_stored']} articles stored "
                f"for {result['symbols']} symbols"
            )
    except Exception as e:
        logger.error(f"Error in news job: {e}")
    finally:
        db.close()


def _run_etoro_price_job(
    session_factory: Callable,
    api_key: str,
    user_key: str,
) -> None:
    """Fetch and store daily eToro portfolio prices."""
    db = session_factory()
    try:
        service = EtoroPriceService(
            db,
            client=EtoroMarketDataClient(api_key=api_key, user_key=user_key),
        )
        result = asyncio.run(service.sync_portfolio_prices())
        if result["status"] == "error":
            logger.error("Daily eToro price job failed: %s", result["errors"])
        else:
            logger.info(
                "Daily eToro price job %s: %s/%s prices updated in %s",
                result["status"],
                result["prices_updated"],
                result["assets"],
                result["currency"],
            )
            if result["errors"]:
                logger.warning("eToro price job partial failures: %s", result["errors"])
    except Exception:
        logger.exception("Daily eToro price job failed")
    finally:
        db.close()


def start_scheduler():
    """Start the scheduler"""
    global scheduler
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped")
