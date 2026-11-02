"""Fetch daily reference exchange rates from Frankfurter."""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

import requests


class FrankfurterFetcher:
    API_URL = "https://api.frankfurter.dev/v2/rates"
    BASE_CURRENCY = "EUR"
    QUOTE_CURRENCIES = ("USD", "GBP", "CHF")

    def fetch_rates(
        self,
        start_date: str | None = None,
    ) -> List[Tuple[date, str, str, Decimal]]:
        """Return (date, base, quote, rate) observations, including a short overlap."""
        if start_date is None:
            start_date = (datetime.utcnow().date() - timedelta(days=7)).isoformat()

        response = requests.get(
            self.API_URL,
            params={
                "from": start_date,
                "base": self.BASE_CURRENCY,
                "quotes": ",".join(self.QUOTE_CURRENCIES),
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected response from Frankfurter: expected a list of rates")

        observations = []
        for item in payload:
            try:
                observation_date = date.fromisoformat(item["date"])
                base_currency = item["base"].upper()
                quote_currency = item["quote"].upper()
                rate = Decimal(str(item["rate"]))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ValueError("Invalid exchange-rate observation from Frankfurter") from exc

            if (
                base_currency != self.BASE_CURRENCY
                or quote_currency not in self.QUOTE_CURRENCIES
                or not rate.is_finite()
                or rate <= 0
            ):
                raise ValueError("Frankfurter returned an unsupported or invalid exchange rate")

            observations.append((observation_date, base_currency, quote_currency, rate))

        return observations
