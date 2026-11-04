"""Valuation agent exposing stored prices and fundamental-data coverage."""

import time
from decimal import Decimal
from typing import Any, Dict, List

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.assessment import build_assessment
from app.models import Asset, AssetType, CompanyFinancialFact, Holding, Price


class ValuationAgent(BaseAgent):
    """Report available valuation inputs without inventing missing metrics."""

    SUPPORTED_TYPES = (AssetType.STOCK, AssetType.ETF)

    def __init__(self) -> None:
        super().__init__(name="valuation")

    async def execute(self, context: AgentContext) -> AgentOutput:
        started = time.monotonic()
        db = context.metadata.get("db")
        if db is None:
            return self._create_output(
                False, {}, "Database session not provided in agent context"
            )

        try:
            assets = (
                db.query(Asset)
                .join(Holding, Holding.asset_id == Asset.id)
                .filter(
                    Holding.quantity > 0,
                    Asset.asset_type.in_(self.SUPPORTED_TYPES),
                )
                .distinct()
                .order_by(Asset.symbol)
                .all()
            )
            valuations: List[Dict[str, Any]] = []
            for asset in assets:
                latest_price = (
                    db.query(Price)
                    .filter(Price.asset_id == asset.id)
                    .order_by(Price.price_date.desc(), Price.id.desc())
                    .first()
                )
                facts = (
                    db.query(CompanyFinancialFact)
                    .filter(CompanyFinancialFact.symbol == asset.symbol)
                    .order_by(
                        CompanyFinancialFact.period_end.desc(),
                        CompanyFinancialFact.filed_date.desc(),
                    )
                    .all()
                )
                latest_facts = {}
                for fact in facts:
                    latest_facts.setdefault(fact.metric, fact)

                def fact_value(metric: str) -> Any:
                    fact = latest_facts.get(metric)
                    if fact is None:
                        return None
                    return {
                        "value": str(fact.value),
                        "units": fact.units,
                        "period_start": (
                            fact.period_start.isoformat() if fact.period_start else None
                        ),
                        "period_end": fact.period_end.isoformat(),
                        "filed_date": fact.filed_date.isoformat(),
                        "form": fact.form,
                        "source": fact.source,
                    }

                eps_fact = latest_facts.get("diluted_eps")
                price_is_usd = bool(
                    latest_price and latest_price.currency == "USD"
                )
                eps_units = (
                    eps_fact.units.casefold().replace(" ", "")
                    if eps_fact is not None
                    else ""
                )
                annual_pe = None
                if (
                    eps_fact is not None
                    and eps_fact.value > 0
                    and price_is_usd
                    and eps_units in {"usd/share", "usd/shares"}
                ):
                    annual_pe = str(latest_price.price / eps_fact.value)

                revenue_fact = latest_facts.get("revenue")
                income_fact = latest_facts.get("net_income")
                profit_margin = None
                if (
                    revenue_fact is not None
                    and income_fact is not None
                    and revenue_fact.value > 0
                    and revenue_fact.period_end == income_fact.period_end
                    and revenue_fact.units == income_fact.units == "USD"
                ):
                    profit_margin = str(
                        income_fact.value / revenue_fact.value * Decimal("100")
                    )

                cash_flow = latest_facts.get("operating_cash_flow")
                capex = latest_facts.get("capital_expenditures")
                free_cash_flow = None
                if (
                    cash_flow is not None
                    and capex is not None
                    and cash_flow.period_end == capex.period_end
                    and cash_flow.units == capex.units == "USD"
                ):
                    free_cash_flow = str(cash_flow.value - capex.value)

                valuations.append({
                        "symbol": asset.symbol,
                        "asset_type": asset.asset_type.value,
                        "latest_price": (
                            str(latest_price.price) if latest_price else None
                        ),
                        "price_currency": (
                            latest_price.currency if latest_price else None
                        ),
                        "price_source": (
                            latest_price.source if latest_price else None
                        ),
                        "price_date": (
                            latest_price.price_date.isoformat()
                            if latest_price
                            else None
                        ),
                        "pe_ratio": annual_pe,
                        "pe_ratio_latest_annual_eps": annual_pe,
                        "pe_ratio_basis": "latest annual diluted EPS",
                        "diluted_eps": fact_value("diluted_eps"),
                        "revenue": fact_value("revenue"),
                        "net_income": fact_value("net_income"),
                        "net_profit_margin_percent": profit_margin,
                        "total_assets": fact_value("total_assets"),
                        "total_liabilities": fact_value("total_liabilities"),
                        "stockholders_equity": fact_value("stockholders_equity"),
                        "operating_cash_flow": fact_value("operating_cash_flow"),
                        "capital_expenditures": fact_value("capital_expenditures"),
                        "free_cash_flow": free_cash_flow,
                        "fundamentals_status": (
                            "available" if latest_facts else "unavailable"
                        ),
                    })

            has_fundamentals = any(
                item["fundamentals_status"] == "available" for item in valuations
            )
            priced_fundamentals = [
                item
                for item in valuations
                if item["pe_ratio"] is not None
            ]
            evidence = []
            for item in valuations:
                if item["pe_ratio"] is not None:
                    eps = item["diluted_eps"]
                    evidence.append(
                        f"{item['symbol']} P/E {Decimal(item['pe_ratio']):.2f}, "
                        f"based on USD {item['latest_price']} from "
                        f"{item['price_source']} on {item['price_date']} and "
                        f"diluted EPS {eps['value']} for the period ending "
                        f"{eps['period_end']} (filed {eps['filed_date']}, "
                        f"{eps['source']})."
                    )
                elif item["fundamentals_status"] == "available":
                    evidence.append(
                        f"{item['symbol']} has SEC facts, but no compatible USD price "
                        "and annual diluted EPS pair for a P/E calculation."
                    )
                else:
                    evidence.append(
                        f"{item['symbol']} has no stored SEC company facts."
                    )
            assessment_missing = [
                "Peer and historical valuation comparisons.",
                "Forward earnings estimates, growth assumptions, and a cash-flow "
                "valuation model.",
            ]
            if any(
                item["price_source"] == "virtual_broker" for item in valuations
            ):
                assessment_missing.append(
                    "A verified current market quote; virtual-broker prices are samples."
                )
            return self._create_output(
                True,
                {
                    "status": (
                        "available"
                        if has_fundamentals
                        else "fundamentals_unavailable"
                        if valuations
                        else "no_eligible_holdings"
                    ),
                    "assets": valuations,
                    "assessment": build_assessment(
                        finding=(
                            "Stored company facts and price records support a "
                            "limited valuation screen, not a conclusion that a "
                            "stock is cheap or expensive."
                            if has_fundamentals
                            else "Insufficient stored company fundamentals to assess valuation."
                        ),
                        evidence=evidence,
                        meaning=(
                            "A trailing P/E relates a stored price to reported annual "
                            "earnings; by itself it says little about future growth or fair value."
                        ),
                        counterpoint=(
                            "A low or high P/E can reflect growth expectations, risks, "
                            "accounting differences, or a stale/sample price."
                        ),
                        confidence=(
                            "High for arithmetic from the cited SEC facts and stored price; "
                            "low for any cheap/expensive judgment."
                        ),
                        missing=assessment_missing,
                    ),
                    "limitations": (
                        [
                            "Financial-statement data is available only for reported filing periods; "
                            "P/E uses the latest annual diluted EPS and current stored USD price."
                        ]
                        if has_fundamentals
                        else [
                            "No SEC company facts have been synced; use the SEC fundamentals sync endpoint."
                        ]
                    ),
                },
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:
            self.logger.exception("Valuation agent failed")
            return self._create_output(
                False,
                {},
                str(exc),
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
