"""
Abstract broker interface and virtual broker implementation
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass


@dataclass
class BrokerHolding:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    currency: str = "EUR"


@dataclass
class BrokerTransaction:
    symbol: str
    transaction_type: str
    quantity: Decimal
    price: Decimal
    timestamp: datetime
    broker_id: str


class BrokerInterface(ABC):
    """Abstract base class for broker integrations"""

    @abstractmethod
    async def get_holdings(self) -> List[BrokerHolding]:
        """Fetch current holdings from broker"""
        pass

    @abstractmethod
    async def get_transactions(self, limit: int = 100) -> List[BrokerTransaction]:
        """Fetch transaction history"""
        pass

    @abstractmethod
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        """Fetch current prices for symbols"""
        pass

    @abstractmethod
    async def place_order(self, symbol: str, quantity: Decimal, price: Decimal, order_type: str) -> str:
        """Place an order (for future use)"""
        pass


class VirtualBroker(BrokerInterface):
    """
    Virtual broker for testing without real API credentials.
    Stores virtual portfolio in memory.
    """

    def __init__(self):
        self.holdings: Dict[str, BrokerHolding] = {}
        self.transactions: List[BrokerTransaction] = []
        self._init_sample_data()

    def _init_sample_data(self):
        """Initialize with sample portfolio for testing"""
        # Sample holdings
        self.holdings = {
            "AAPL": BrokerHolding(
                symbol="AAPL",
                quantity=Decimal("10"),
                average_cost=Decimal("150.00"),
                current_price=Decimal("175.50"),
                currency="USD"
            ),
            "MSFT": BrokerHolding(
                symbol="MSFT",
                quantity=Decimal("5"),
                average_cost=Decimal("300.00"),
                current_price=Decimal("350.25"),
                currency="USD"
            ),
            "VOO": BrokerHolding(
                symbol="VOO",
                quantity=Decimal("20"),
                average_cost=Decimal("350.00"),
                current_price=Decimal("425.75"),
                currency="USD"
            ),
        }

        # Sample transactions
        self.transactions = [
            BrokerTransaction(
                symbol="AAPL",
                transaction_type="buy",
                quantity=Decimal("10"),
                price=Decimal("150.00"),
                timestamp=datetime(2024, 1, 15, 10, 30),
                broker_id="SC_TXN_001"
            ),
            BrokerTransaction(
                symbol="MSFT",
                transaction_type="buy",
                quantity=Decimal("5"),
                price=Decimal("300.00"),
                timestamp=datetime(2024, 1, 20, 14, 45),
                broker_id="SC_TXN_002"
            ),
        ]

    async def get_holdings(self) -> List[BrokerHolding]:
        return list(self.holdings.values())

    async def get_transactions(self, limit: int = 100) -> List[BrokerTransaction]:
        return self.transactions[-limit:]

    async def get_current_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        prices = {}
        for symbol in symbols:
            if symbol in self.holdings:
                prices[symbol] = self.holdings[symbol].current_price
        return prices

    async def place_order(self, symbol: str, quantity: Decimal, price: Decimal, order_type: str) -> str:
        # Virtual implementation - just return a mock order ID
        return f"VIRTUAL_ORDER_{symbol}_{datetime.now().timestamp()}"

    def add_holding(self, symbol: str, holding: BrokerHolding):
        """For testing: add a holding"""
        self.holdings[symbol] = holding

    def add_transaction(self, transaction: BrokerTransaction):
        """For testing: add a transaction"""
        self.transactions.append(transaction)


class ScalableCapitalBroker(BrokerInterface):
    """Scalable Capital broker integration (stub - will be implemented later)"""

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    async def get_holdings(self) -> List[BrokerHolding]:
        # TODO: Implement API call to Scalable Capital
        raise NotImplementedError("Scalable Capital integration coming soon")

    async def get_transactions(self, limit: int = 100) -> List[BrokerTransaction]:
        raise NotImplementedError("Scalable Capital integration coming soon")

    async def get_current_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        raise NotImplementedError("Scalable Capital integration coming soon")

    async def place_order(self, symbol: str, quantity: Decimal, price: Decimal, order_type: str) -> str:
        raise NotImplementedError("Scalable Capital integration coming soon")


class BinanceBroker(BrokerInterface):
    """Binance broker integration (stub - will be implemented later)"""

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    async def get_holdings(self) -> List[BrokerHolding]:
        # TODO: Implement API call to Binance
        raise NotImplementedError("Binance integration coming soon")

    async def get_transactions(self, limit: int = 100) -> List[BrokerTransaction]:
        raise NotImplementedError("Binance integration coming soon")

    async def get_current_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        raise NotImplementedError("Binance integration coming soon")

    async def place_order(self, symbol: str, quantity: Decimal, price: Decimal, order_type: str) -> str:
        raise NotImplementedError("Binance integration coming soon")
