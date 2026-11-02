import logging
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.services import ExchangeRateService, MacroDataService

logger = logging.getLogger(__name__)

scheduler = None


def init_scheduler(session_factory: Callable, fred_api_key: Optional[str] = None):
    """Initialize daily FX ingestion and optional FRED macro jobs."""
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

    logger.info("APScheduler initialized with exchange-rate and configured macro jobs")
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
