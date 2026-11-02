"""Manually run the live FRED-to-database integration check."""
import logging

from app.config import settings
from app.database import get_session_factory
from app.services import MacroDataService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    if not settings.fred_api_key:
        print("Skipped: set FRED_API_KEY to run the live integration check.")
        return 0

    db = get_session_factory()()
    try:
        service = MacroDataService(db, settings.fred_api_key)
        daily_result = service.fetch_and_store_daily_macro()
        monthly_result = service.fetch_and_store_monthly_macro()

        results = {
            "daily": daily_result,
            "monthly": monthly_result,
        }
        for job, result in results.items():
            print(f"{job}: {result}")
            if result.get("status") != "success":
                return 1

        latest = service.get_latest_macro_data()
        if not latest:
            logger.error("FRED jobs completed but no macro observations are stored.")
            return 1

        print("Latest stored observations:")
        for series_id, observation in latest.items():
            print(
                f"  {series_id}: {observation['value']} "
                f"{observation['units']} ({observation['date']})"
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
