"""Portfolio analysis tools that agents can use."""

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool


@tool
def get_max_holding(
    holdings: List[Dict[str, Any]],
    key: str = "current_value"
) -> Optional[Dict[str, Any]]:
    """
    Get holding with maximum value for given key.
    Agents use this to find biggest position, best performer, etc.

    Args:
        holdings: List of holding dicts
        key: Field to compare (current_value, gain_loss, gain_loss_percent)

    Returns:
        Holding dict with max value, or None if empty

    Example:
        biggest = get_max_holding(holdings, "current_value")
        best_performer = get_max_holding(holdings, "gain_loss_percent")
    """
    if not holdings:
        return None

    return max(
        holdings,
        key=lambda h: float(h.get(key, 0))
    )


@tool
def get_min_holding(
    holdings: List[Dict[str, Any]],
    key: str = "current_value"
) -> Optional[Dict[str, Any]]:
    """
    Get holding with minimum value for given key.
    Agents use this to find smallest position, worst performer, etc.

    Args:
        holdings: List of holding dicts
        key: Field to compare (current_value, gain_loss, gain_loss_percent)

    Returns:
        Holding dict with min value, or None if empty

    Example:
        smallest = get_min_holding(holdings, "current_value")
        worst_performer = get_min_holding(holdings, "gain_loss_percent")
    """
    if not holdings:
        return None

    return min(
        holdings,
        key=lambda h: float(h.get(key, 0))
    )


@tool
def get_holding_by_symbol(
    holdings: List[Dict[str, Any]],
    symbol: str
) -> Optional[Dict[str, Any]]:
    """
    Get specific holding by stock symbol.
    Agents use this to look up individual positions.

    Args:
        holdings: List of holding dicts
        symbol: Stock ticker (e.g., "AAPL", "MSFT")

    Returns:
        Holding dict matching symbol, or None if not found

    Example:
        apple = get_holding_by_symbol(holdings, "AAPL")
    """
    if not holdings or not symbol:
        return None

    symbol = symbol.upper()
    return next(
        (h for h in holdings if h.get("symbol", "").upper() == symbol),
        None
    )


@tool
def filter_holdings_by_intent(
    holdings: List[Dict[str, Any]],
    intent_type: str,
    intent_detail: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Filter holdings based on question intent.
    Agents use this to narrow down holdings based on what user asked.

    Args:
        holdings: All holdings
        intent_type: Type of question
            - "superlative": asking for max/min/best/worst
            - "specific_holding": asking about one stock
            - "general": asking for all holdings
        intent_detail: Detail of intent
            - For superlative: "max_by_value", "min_by_value", "best_gain", "worst_gain"
            - For specific_holding: the ticker symbol (e.g., "AAPL")
            - For general: None

    Returns:
        Filtered list of holdings (usually 0-1 for specific queries, all for general)

    Example:
        biggest = filter_holdings_by_intent(holdings, "superlative", "max_by_value")
        apple = filter_holdings_by_intent(holdings, "specific_holding", "AAPL")
        all_holdings = filter_holdings_by_intent(holdings, "general", None)
    """
    if not holdings:
        return []

    if intent_type == "superlative":
        if intent_detail == "max_by_value":
            holding = get_max_holding(holdings, "current_value")
            return [holding] if holding else []

        elif intent_detail == "min_by_value":
            holding = get_min_holding(holdings, "current_value")
            return [holding] if holding else []

        elif intent_detail == "best_gain":
            holding = get_max_holding(holdings, "gain_loss_percent")
            return [holding] if holding else []

        elif intent_detail == "worst_gain":
            holding = get_min_holding(holdings, "gain_loss_percent")
            return [holding] if holding else []

        elif intent_detail == "biggest_gain_dollars":
            holding = get_max_holding(holdings, "gain_loss")
            return [holding] if holding else []

        elif intent_detail == "biggest_loss_dollars":
            holding = get_min_holding(holdings, "gain_loss")
            return [holding] if holding else []

    elif intent_type == "specific_holding":
        holding = get_holding_by_symbol(holdings, intent_detail)
        return [holding] if holding else []

    elif intent_type == "general":
        return holdings

    return holdings


@tool
def format_holdings_response(
    holdings: List[Dict[str, Any]],
    title: str = "Holdings"
) -> str:
    """
    Format holdings list as readable string.
    Agents use this to create natural language responses.

    Args:
        holdings: List of holding dicts
        title: Header for the response

    Returns:
        Formatted string representation

    Example:
        text = format_holdings_response([aapl_holding], "Your Apple Position")
    """
    if not holdings:
        return "No holdings found."

    lines = [f"{title}:"]

    for holding in holdings:
        symbol = holding.get("symbol", "Unknown")
        quantity = holding.get("quantity", 0)
        price = holding.get("price", 0)
        current_value = holding.get("current_value", 0)
        gain_loss = holding.get("gain_loss", 0)
        gain_loss_percent = holding.get("gain_loss_percent", 0)

        lines.append(f"\n{symbol}:")
        lines.append(f"  Quantity: {quantity} units @ USD {price}")
        lines.append(f"  Current Value: USD {current_value}")
        lines.append(f"  Gain/Loss: USD {gain_loss} ({gain_loss_percent}%)")

    return "\n".join(lines)


@tool
def get_portfolio_summary(
    holdings: List[Dict[str, Any]],
    total_value: float,
    total_gain_loss: float,
    total_gain_loss_percent: float
) -> str:
    """
    Format portfolio summary with concentration info.
    Agents use this to create overview of entire portfolio.

    Args:
        holdings: All holdings
        total_value: Total portfolio value
        total_gain_loss: Total gain/loss in dollars
        total_gain_loss_percent: Total gain/loss percentage

    Returns:
        Formatted summary string with concentration breakdown

    Example:
        summary = get_portfolio_summary(
            holdings,
            14821.25,
            2221.25,
            17.63
        )
    """
    lines = [
        f"Portfolio Summary:",
        f"  Total Value: USD {total_value:,.2f}",
        f"  Total Gain/Loss: USD {total_gain_loss:,.2f} ({total_gain_loss_percent:.2f}%)",
        f"  Holdings: {len(holdings)}",
        f"\nConcentration:",
    ]

    # Calculate and show concentration for each holding
    for holding in sorted(holdings, key=lambda h: float(h.get("current_value", 0)), reverse=True):
        symbol = holding.get("symbol", "Unknown")
        value = float(holding.get("current_value", 0))
        weight = (value / total_value * 100) if total_value > 0 else 0
        lines.append(f"  {symbol}: {weight:.2f}% (USD {value:,.2f})")

    return "\n".join(lines)


@tool
def calculate_concentration(
    holdings: List[Dict[str, Any]],
    total_value: float
) -> Dict[str, float]:
    """
    Calculate concentration percentages for all holdings.
    Agents use this for risk analysis.

    Args:
        holdings: All holdings
        total_value: Total portfolio value

    Returns:
        Dict mapping symbol to concentration percentage

    Example:
        conc = calculate_concentration(holdings, 14821.25)
        # Returns: {"AAPL": 11.84, "MSFT": 11.82, "VOO": 57.45, "NVDA": 18.89}
    """
    concentrations = {}

    for holding in holdings:
        symbol = holding.get("symbol", "Unknown")
        value = float(holding.get("current_value", 0))
        weight = (value / total_value * 100) if total_value > 0 else 0
        concentrations[symbol] = weight

    return concentrations


# Export all tools
PORTFOLIO_TOOLS = [
    get_max_holding,
    get_min_holding,
    get_holding_by_symbol,
    filter_holdings_by_intent,
    format_holdings_response,
    get_portfolio_summary,
    calculate_concentration,
]
