"""SEC EDGAR Company Facts client and fact selection."""

from datetime import date
from typing import Any, Dict, List, Optional

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

FACT_SPECS = {
    "revenue": {
        "tags": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "Revenues",
        ),
        "duration": True,
    },
    "net_income": {"tags": ("NetIncomeLoss", "ProfitLoss"), "duration": True},
    "diluted_eps": {"tags": ("EarningsPerShareDiluted",), "duration": True},
    "operating_cash_flow": {
        "tags": ("NetCashProvidedByUsedInOperatingActivities",),
        "duration": True,
    },
    "capital_expenditures": {
        "tags": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
        "duration": True,
    },
    "total_assets": {"tags": ("Assets",), "duration": False},
    "total_liabilities": {"tags": ("Liabilities",), "duration": False},
    "stockholders_equity": {
        "tags": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "duration": False,
    },
}


def build_ticker_map(payload: Dict[str, Any]) -> Dict[str, str]:
    """Map uppercase ticker symbols to zero-padded SEC CIK identifiers."""
    entries = payload.values() if isinstance(payload, dict) else payload
    result = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker")
        cik = item.get("cik_str")
        if ticker and cik is not None:
            result[str(ticker).upper()] = str(cik).zfill(10)
    return result


def extract_company_facts(
    payload: Dict[str, Any],
    current_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Select the latest annual income/cash-flow and reported balance-sheet facts."""
    today = current_date or date.today()
    gaap_facts = payload.get("facts", {}).get("us-gaap", {})
    selected = []

    for metric, spec in FACT_SPECS.items():
        candidates = []
        for tag in spec["tags"]:
            fact = gaap_facts.get(tag)
            if not isinstance(fact, dict):
                continue
            for unit, observations in fact.get("units", {}).items():
                for observation in observations:
                    form = observation.get("form")
                    filed = observation.get("filed")
                    end = observation.get("end")
                    if form not in {"10-K", "10-Q"} or not filed or not end:
                        continue
                    try:
                        filed_date = date.fromisoformat(filed)
                        period_end = date.fromisoformat(end)
                    except ValueError:
                        continue
                    if filed_date > today:
                        continue

                    period_start = None
                    if spec["duration"]:
                        start = observation.get("start")
                        if form != "10-K" or observation.get("fp") != "FY" or not start:
                            continue
                        try:
                            period_start = date.fromisoformat(start)
                        except ValueError:
                            continue
                        duration_days = (period_end - period_start).days
                        if not 330 <= duration_days <= 380:
                            continue

                    accession = observation.get("accn")
                    if not accession:
                        continue
                    try:
                        value = str(observation["val"])
                    except KeyError:
                        continue
                    candidates.append(
                        {
                            "metric": metric,
                            "value": value,
                            "units": unit,
                            "period_start": period_start,
                            "period_end": period_end,
                            "filed_date": filed_date,
                            "form": form,
                            "accession_number": accession,
                        }
                    )
        if candidates:
            candidates.sort(
                key=lambda item: (item["period_end"], item["filed_date"]),
                reverse=True,
            )
            selected.append(candidates[0])

    return selected


def extract_annual_fact_history(
    payload: Dict[str, Any],
    current_date: Optional[date] = None,
    limit: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return recent comparable annual income and cash-flow observations."""
    if limit < 1:
        raise ValueError("limit must be positive")

    today = current_date or date.today()
    gaap_facts = payload.get("facts", {}).get("us-gaap", {})
    history: Dict[str, List[Dict[str, Any]]] = {}

    for metric, spec in FACT_SPECS.items():
        if not spec["duration"]:
            continue
        candidates = []
        for tag in spec["tags"]:
            fact = gaap_facts.get(tag)
            if not isinstance(fact, dict):
                continue
            for unit, observations in fact.get("units", {}).items():
                for observation in observations:
                    if (
                        observation.get("form") != "10-K"
                        or observation.get("fp") != "FY"
                    ):
                        continue
                    filed = observation.get("filed")
                    start = observation.get("start")
                    end = observation.get("end")
                    accession = observation.get("accn")
                    if not filed or not start or not end or not accession:
                        continue
                    try:
                        filed_date = date.fromisoformat(filed)
                        period_start = date.fromisoformat(start)
                        period_end = date.fromisoformat(end)
                        value = str(observation["val"])
                    except (ValueError, KeyError):
                        continue
                    duration_days = (period_end - period_start).days
                    if (
                        filed_date > today
                        or not 330 <= duration_days <= 380
                    ):
                        continue
                    candidates.append(
                        {
                            "metric": metric,
                            "value": value,
                            "units": unit,
                            "period_start": period_start,
                            "period_end": period_end,
                            "filed_date": filed_date,
                            "form": "10-K",
                            "accession_number": accession,
                        }
                    )
        candidates.sort(
            key=lambda item: (item["period_end"], item["filed_date"]),
            reverse=True,
        )
        newest_by_period = {}
        for candidate in candidates:
            newest_by_period.setdefault(
                (candidate["period_end"], candidate["units"]), candidate
            )
        candidates = list(newest_by_period.values())
        if candidates:
            history[metric] = candidates[:limit]
    return history
