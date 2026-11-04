"""Macro context agent for the latest stored economic indicators."""

import time
from datetime import date
from decimal import Decimal
from typing import Any, Dict

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.assessment import build_assessment
from app.models import MacroIndicator
from app.data_sources.fred import FREDFetcher


INDICATOR_MEANING = {
    "VIXCLS": (
        "The VIX reflects option-implied near-term equity volatility, not the "
        "direction of the market."
    ),
    "DFF": (
        "The effective federal funds rate is a short-term policy-rate measure; "
        "it does not by itself predict equity returns."
    ),
    "DGS10": (
        "The 10-year Treasury yield can affect discount rates and financing "
        "conditions, but its impact varies by company."
    ),
    "CPIAUCSL": (
        "CPI is a price-level index; one observation is not an inflation rate "
        "or a complete inflation trend."
    ),
}


class MacroContextAgent(BaseAgent):
    """Provide dated macro observations and explicit data-availability limits."""

    def __init__(self) -> None:
        super().__init__(name="macro")

    async def execute(self, context: AgentContext) -> AgentOutput:
        started = time.monotonic()
        db = context.metadata.get("db")
        if db is None:
            return self._create_output(
                False, {}, "Database session not provided in agent context"
            )

        try:
            indicators: Dict[str, Any] = {}
            for series_id, series_info in FREDFetcher.SERIES.items():
                observations = (
                    db.query(MacroIndicator)
                    .filter(MacroIndicator.series_id == series_id)
                    .order_by(MacroIndicator.date.desc())
                    .limit(2)
                    .all()
                )
                if observations:
                    latest = observations[0]
                    previous = observations[1] if len(observations) > 1 else None
                    latest_value = Decimal(str(latest.value))
                    indicators[series_id] = {
                        "name": series_info["name"],
                        "value": str(latest_value),
                        "units": latest.units,
                        "date": latest.date.date().isoformat(),
                        "source": latest.source,
                        "fetched_at": (
                            latest.fetched_at.isoformat()
                            if latest.fetched_at
                            else None
                        ),
                        "previous": (
                            {
                                "value": str(previous.value),
                                "date": previous.date.date().isoformat(),
                            }
                            if previous
                            else None
                        ),
                        "change_from_previous": (
                            str(latest_value - Decimal(str(previous.value)))
                            if previous
                            else None
                        ),
                    }

            evidence = [
                (
                    f"{item['name']}: {item['value']} {item['units']} on "
                    f"{item['date']} ({item['source']})"
                    + (
                        f"; change from {item['previous']['date']} is "
                        f"{item['change_from_previous']} {item['units']}."
                        if item["previous"]
                        else "."
                    )
                )
                for item in indicators.values()
            ]
            stale_indicators = []
            for series_id, item in indicators.items():
                observed = date.fromisoformat(item["date"])
                max_age_days = 60 if series_id == "CPIAUCSL" else 10
                if (date.today() - observed).days > max_age_days:
                    stale_indicators.append(
                        f"{item['name']} observation is older than {max_age_days} days."
                    )
            if stale_indicators:
                evidence.extend(stale_indicators)
            if not evidence:
                evidence.append("No observations were found in the macro data store.")
            indicator_meanings = [
                INDICATOR_MEANING[series_id]
                for series_id in indicators
                if series_id in INDICATOR_MEANING
            ]
            meaning = (
                " ".join(indicator_meanings)
                + " These observations do not establish an economic regime or "
                "predict the performance of an individual holding."
                if indicator_meanings
                else (
                    "These indicators provide limited background context; they do "
                    "not establish an economic regime or predict the performance "
                    "of an individual holding."
                )
            )

            return self._create_output(
                True,
                {
                    "status": "available" if indicators else "no_data",
                    "indicators": indicators,
                    "assessment": build_assessment(
                        finding=(
                            f"Stored FRED observations are available for "
                            f"{len(indicators)} indicators."
                            if indicators
                            else "No stored macroeconomic observations are available."
                        ),
                        evidence=evidence,
                        meaning=meaning,
                        counterpoint=(
                            "Macro series update at different frequencies and may "
                            "lag current conditions; market effects are uncertain."
                        ),
                        confidence=(
                            "High that these are the stored observations; low for "
                            "their currentness or investment implications."
                            if indicators
                            else "No conclusion can be drawn without observations."
                        ),
                        missing=(
                            stale_indicators
                            + [
                                "Recent and historical context for each series.",
                                "A direct link from macro conditions to each holding.",
                            ]
                        ),
                    ),
                    "limitations": (
                        stale_indicators
                        if indicators
                        else ["No macroeconomic observations are stored."]
                    ),
                },
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:
            self.logger.exception("Macro context agent failed")
            return self._create_output(
                False,
                {},
                str(exc),
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
