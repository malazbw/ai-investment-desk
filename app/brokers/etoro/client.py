"""Async client for eToro's documented public market-data API."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import uuid4

import httpx


class EtoroAPIError(RuntimeError):
    """Raised when eToro rejects a request or returns invalid data."""


@dataclass(frozen=True)
class EtoroQuote:
    instrument_id: int
    price_usd: Decimal
    price_date: datetime


class EtoroMarketDataClient:
    API_BASE_URL = "https://public-api.etoro.com"
    MAX_INSTRUMENTS_PER_REQUEST = 100

    def __init__(
        self,
        api_key: str,
        user_key: str,
        *,
        base_url: str = API_BASE_URL,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not api_key or not user_key:
            raise ValueError("Both ETORO_API_KEY and ETORO_USER_KEY are required")

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"x-api-key": api_key, "x-user-key": user_key},
            timeout=20.0,
            transport=transport,
        )

    async def __aenter__(self) -> "EtoroMarketDataClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.aclose()

    async def resolve_instrument_id(self, symbol: str) -> Optional[int]:
        """Resolve a ticker only when eToro returns an exact symbol match."""
        payload = await self._get(
            "/api/v1/market-data/search",
            params={"internalSymbolFull": symbol},
        )
        items = payload.get("items")
        if not isinstance(items, list):
            raise EtoroAPIError("eToro instrument search returned an invalid response")

        for item in items:
            if not isinstance(item, dict):
                continue
            matched_symbol = item.get("internalSymbolFull")
            instrument_id = item.get("instrumentId")
            if (
                isinstance(matched_symbol, str)
                and matched_symbol.upper() == symbol.upper()
                and isinstance(instrument_id, int)
                and not isinstance(instrument_id, bool)
                and instrument_id > 0
                and item.get("isDelisted") is not True
            ):
                return instrument_id
        return None

    async def get_quotes(self, instrument_ids: list[int]) -> dict[int, EtoroQuote]:
        """Fetch current quotes and normalize them to USD."""
        if not instrument_ids:
            return {}
        if len(instrument_ids) > self.MAX_INSTRUMENTS_PER_REQUEST:
            raise ValueError("eToro accepts at most 100 instrument IDs per quote request")
        if any(instrument_id <= 0 for instrument_id in instrument_ids):
            raise ValueError("eToro instrument IDs must be positive integers")

        payload = await self._get(
            "/api/v1/market-data/instruments/rates",
            params={"instrumentIds": ",".join(map(str, instrument_ids))},
        )
        rates = payload.get("rates")
        if not isinstance(rates, list):
            raise EtoroAPIError("eToro rates endpoint returned an invalid response")

        quotes = {}
        for rate in rates:
            if not isinstance(rate, dict):
                continue
            raw_id = rate.get("instrumentID")
            if not isinstance(raw_id, int) or isinstance(raw_id, bool):
                continue

            price = self._decimal(rate.get("lastExecution"))
            if price is None:
                price = self._midpoint(
                    self._decimal(rate.get("bid")),
                    self._decimal(rate.get("ask")),
                )
            conversion = self._midpoint(
                self._decimal(rate.get("conversionRateBid")),
                self._decimal(rate.get("conversionRateAsk")),
            )
            if price is None or price <= 0 or conversion is None or conversion <= 0:
                continue

            raw_date = rate.get("date")
            if not isinstance(raw_date, str):
                continue
            try:
                price_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            if price_date.tzinfo is None:
                price_date = price_date.replace(tzinfo=timezone.utc)
            price_date = price_date.astimezone(timezone.utc).replace(tzinfo=None)

            quotes[raw_id] = EtoroQuote(
                instrument_id=raw_id,
                price_usd=price * conversion,
                price_date=price_date,
            )
        return quotes

    async def _get(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            try:
                response = await self._client.get(
                    path,
                    params=params,
                    headers={"x-request-id": str(uuid4())},
                )
            except httpx.HTTPError as exc:
                raise EtoroAPIError(f"eToro request failed: {exc}") from exc

            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = max(1.0, min(float(retry_after), 60.0))
                except (TypeError, ValueError):
                    delay = float(2**attempt)
                await asyncio.sleep(delay)
                continue
            if response.is_error:
                raise EtoroAPIError(
                    f"eToro API returned HTTP {response.status_code}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise EtoroAPIError("eToro API returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise EtoroAPIError("eToro API returned an invalid response")
            return payload

        raise EtoroAPIError("eToro API rate limit remained exceeded after retries")

    @staticmethod
    def _decimal(value: Any) -> Optional[Decimal]:
        if value is None or isinstance(value, bool):
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
        return result if result.is_finite() else None

    @staticmethod
    def _midpoint(
        first: Optional[Decimal],
        second: Optional[Decimal],
    ) -> Optional[Decimal]:
        if first is not None and second is not None:
            return (first + second) / Decimal("2")
        return first if first is not None else second
