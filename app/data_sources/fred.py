import requests
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FREDFetcher:
    """Fetch macroeconomic data from FRED API"""

    FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"

    SERIES = {
        "VIXCLS": {"name": "VIX Index", "units": "index"},
        "DFF": {"name": "Federal Funds Rate", "units": "percent"},
        "DGS10": {"name": "10-Year Treasury Yield", "units": "percent"},
        "CPIAUCSL": {"name": "Consumer Price Index", "units": "index"},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_series(self, series_id: str, start_date: str = None) -> List[Tuple[str, Decimal]]:
        """
        Fetch data for a single FRED series with retry logic
        Returns: List of (date_str, value) tuples
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "observation_start": start_date,
            "file_type": "json",
        }

        retry_delays = [5, 15]
        attempt = 0

        while attempt <= len(retry_delays):
            try:
                response = requests.get(
                    self.FRED_API_URL,
                    params=params,
                    timeout=10
                )
                response.raise_for_status()

                data = response.json()

                if "observations" not in data:
                    logger.error("FRED response omitted observations for %s", series_id)
                    raise RuntimeError(
                        f"FRED response omitted observations for series {series_id}"
                    )

                observations = data["observations"]
                results = []

                for obs in observations:
                    if obs["value"] != ".":
                        try:
                            results.append((obs["date"], Decimal(obs["value"])))
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid value for {series_id} on {obs['date']}: {obs['value']}")

                logger.info(f"Successfully fetched {len(results)} observations for {series_id}")
                return results

            except requests.exceptions.RequestException as e:
                attempt += 1

                if attempt <= len(retry_delays):
                    delay = retry_delays[attempt - 1]
                    logger.warning(
                        "FRED fetch failed for %s; retry %s after %s seconds",
                        series_id,
                        attempt,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error("FRED fetch failed for %s after all retries", series_id)
                    raise RuntimeError(
                        f"FRED request failed for series {series_id}"
                    ) from None

            except Exception as e:
                logger.error(
                    "Unexpected error fetching FRED series %s: %s",
                    series_id,
                    type(e).__name__,
                )
                raise RuntimeError(
                    f"Unexpected response while fetching FRED series {series_id}"
                ) from None

        return []

    def fetch_daily_series(self, start_date: str = None) -> Dict[str, List[Tuple[str, Decimal]]]:
        """Fetch VIX, DFF, DGS10 (daily-updating series)"""
        daily_series = ["VIXCLS", "DFF", "DGS10"]
        results = {}

        for series_id in daily_series:
            results[series_id] = self.fetch_series(series_id, start_date)

        return results

    def fetch_monthly_series(self, start_date: str = None) -> Dict[str, List[Tuple[str, Decimal]]]:
        """Fetch CPIAUCSL (monthly-updating series)"""
        return {"CPIAUCSL": self.fetch_series("CPIAUCSL", start_date)}
