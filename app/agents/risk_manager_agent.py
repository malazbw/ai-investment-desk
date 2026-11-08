"""Deterministic portfolio concentration and price-coverage analysis."""

import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.assessment import build_assessment
from app.agents.findings import Finding, SourceRef, SourceType, EvidenceLevel
from app.models import Asset, Holding, Price


class RiskManagerAgent(BaseAgent):
    """Estimate USD position weights and concentration from stored USD prices."""

    def __init__(self) -> None:
        super().__init__(name="risk")

    async def execute(self, context: AgentContext) -> AgentOutput:
        started = time.monotonic()
        db = context.metadata.get("db")
        if db is None:
            return self._create_output(
                False, {}, "Database session not provided in agent context"
            )

        try:
            holdings = (
                db.query(Holding, Asset)
                .join(Asset, Asset.id == Holding.asset_id)
                .filter(Holding.quantity > 0)
                .order_by(Asset.symbol)
                .all()
            )
            by_symbol: Dict[str, Dict[str, Any]] = {}
            missing_prices = set()
            for holding, asset in holdings:
                position = by_symbol.setdefault(
                    asset.symbol,
                    {
                        "symbol": asset.symbol,
                        "quantity": Decimal("0"),
                        "value_usd": Decimal("0"),
                        "price_source": None,
                    },
                )
                position["quantity"] += holding.quantity

            for symbol, position in by_symbol.items():
                asset = db.query(Asset).filter(Asset.symbol == symbol).one()
                latest_price = (
                    db.query(Price)
                    .filter(Price.asset_id == asset.id)
                    .order_by(Price.price_date.desc(), Price.id.desc())
                    .first()
                )
                if latest_price is None or latest_price.currency != "USD":
                    missing_prices.add(symbol)
                    continue
                position["value_usd"] = position["quantity"] * latest_price.price
                position["price_date"] = latest_price.price_date.isoformat()
                position["price_source"] = latest_price.source

            valued = [
                position
                for position in by_symbol.values()
                if position["value_usd"] > 0
            ]
            total_value = sum(
                (position["value_usd"] for position in valued),
                Decimal("0"),
            )
            valued.sort(key=lambda position: position["value_usd"], reverse=True)
            for position in valued:
                position["weight_percent"] = (
                    position["value_usd"] / total_value * Decimal("100")
                )
                position["value_usd"] = str(position["value_usd"])
                position["weight_percent"] = str(position["weight_percent"])
                position["quantity"] = str(position["quantity"])

            largest = valued[0] if valued else None
            assessment_finding = (
                f"{largest['symbol']} is {Decimal(largest['weight_percent']):.2f}% "
                "of the positions with stored USD prices."
                if largest
                else "No positions can be valued from stored USD prices."
            )
            assessment_evidence = [
                f"{len(valued)} of {len(by_symbol)} positions were valued; "
                f"their stored total is USD {total_value}."
            ]
            if largest:
                assessment_evidence.append(
                    f"{largest['symbol']} price source: {largest['price_source']}; "
                    f"price date: {largest['price_date']}."
                )
            assessment_missing = [
                "Unpriced holdings are excluded from concentration percentages.",
                "This calculation does not measure volatility, correlation, liquidity, "
                "or the investor's risk capacity.",
            ]
            if "virtual_broker" in {
                position["price_source"] for position in valued
            }:
                assessment_missing.append(
                    "Virtual-broker prices are sample data, not live market quotes."
                )

            limitations = []
            if missing_prices:
                limitations.append(
                    "USD market prices are unavailable for: "
                    + ", ".join(sorted(missing_prices))
                )
            if total_value == 0:
                limitations.append("No positions with stored USD prices can be valued.")
            if valued:
                limitations.append(
                    "Weights include only positions with stored USD prices; "
                    "unpriced holdings are excluded from the denominator."
                )

            # Extract structured findings for risk analysis
            risk_findings: List[Finding] = []

            # Add findings for each valued position
            for position in valued[:10]:  # Top 10 positions
                risk_findings.append(Finding(
                    claim=f"{position['symbol']}: {position['weight_percent']}% of portfolio (USD {position['value_usd']})",
                    source=SourceRef(
                        source_type=SourceType.PRICE_DATA,
                        source_name=position["price_source"],
                        url=None,
                        credibility_score=1.0 if position["price_source"] != "virtual_broker" else 0.3,
                        fetched_at=datetime.fromisoformat(position["price_date"]) if position.get("price_date") else datetime.utcnow()
                    ),
                    evidence_level=EvidenceLevel.PRIMARY if position["price_source"] != "virtual_broker" else EvidenceLevel.SECONDARY,
                    confidence_score=1.0 if position["price_source"] != "virtual_broker" else 0.5,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "symbol": position["symbol"],
                        "weight_percent": position["weight_percent"],
                        "value_usd": position["value_usd"],
                        "quantity": position["quantity"],
                        "price_source": position["price_source"],
                        "price_date": position.get("price_date")
                    }
                ))

            # Add concentration finding
            if largest:
                risk_findings.append(Finding(
                    claim=f"Largest position concentration: {largest['symbol']} at {Decimal(largest['weight_percent']):.2f}%",
                    source=SourceRef(
                        source_type=SourceType.PORTFOLIO_DATA,
                        source_name="Portfolio Analysis",
                        url=None,
                        credibility_score=1.0,
                        fetched_at=datetime.utcnow()
                    ),
                    evidence_level=EvidenceLevel.DERIVED,
                    confidence_score=0.9,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "largest_symbol": largest["symbol"],
                        "weight_percent": largest["weight_percent"],
                        "positions_counted": len(valued),
                        "total_portfolio_usd": str(total_value)
                    }
                ))

            return self._create_output(
                True,
                {
                    "findings": [f.to_dict() for f in risk_findings],  # NEW: Structured findings
                    "assessment": build_assessment(
                        finding=assessment_finding,
                        evidence=assessment_evidence,
                        meaning=(
                            "A large single-name weight can make portfolio results "
                            "more dependent on that company's performance."
                            if largest
                            else "Concentration cannot be assessed without usable prices."
                        ),
                        counterpoint=(
                            "A position weight alone does not establish that the "
                            "position is too risky or predict a loss."
                        ),
                        confidence=(
                            "High for weights calculated from stored USD prices; "
                            "limited for total-portfolio risk when records are missing "
                            "or sample-based."
                        ),
                        missing=assessment_missing,
                    ),
                    # Keep legacy fields for backward compatibility
                    "status": "available" if valued else "insufficient_price_data",
                    "valuation_currency": "USD",
                    "valued_positions": len(valued),
                    "unpriced_symbols": sorted(missing_prices),
                    "total_valued_usd": str(total_value),
                    "largest_positions": valued[:5],
                    "limitations": limitations,
                },
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:
            self.logger.exception("Risk manager agent failed")
            return self._create_output(
                False,
                {},
                str(exc),
                execution_time_ms=(time.monotonic() - started) * 1000,
            )
