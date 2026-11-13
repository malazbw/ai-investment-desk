"""Portfolio tools service - provides tool execution interface for agents"""

import logging
from app.models import Holding, Asset, Price, Transaction
from decimal import Decimal

logger = logging.getLogger(__name__)


class PortfolioToolsService:
    """Service that executes portfolio analysis tools with database access"""

    def __init__(self, db_factory):
        """Initialize tools service with database factory"""
        self.db_factory = db_factory
        self._tools = self._register_tools()
        logger.info("PortfolioToolsService initialized with %d tools", len(self._tools))

    def _register_tools(self):
        """Register all available tools"""
        return {
            "get_portfolio_summary": self._get_portfolio_summary,
            "get_max_holding": self._get_max_holding,
            "get_min_holding": self._get_min_holding,
            "get_all_holdings": self._get_all_holdings,
            "get_recent_transactions": self._get_recent_transactions,
        }

    def _holding_to_dict(self, holding):
        """Convert holding ORM object to dict"""
        if isinstance(holding, dict):
            return holding

        asset = holding.asset

        # Calculate gain/loss
        gain_loss = None
        gain_loss_percent = None
        if holding.current_value is not None and holding.total_cost:
            gain_loss = float(holding.current_value) - float(holding.total_cost)
            gain_loss_percent = (gain_loss / float(holding.total_cost) * 100) if float(holding.total_cost) > 0 else 0

        return {
            "symbol": asset.symbol if asset else "unknown",
            "name": asset.name if asset else "unknown",
            "quantity": str(holding.quantity),
            "average_cost": str(holding.average_cost),
            "total_cost": str(holding.total_cost),
            "current_price": str(holding.current_price) if holding.current_price is not None else None,
            "current_value": str(holding.current_value) if holding.current_value is not None else None,
            "gain_loss": str(gain_loss) if gain_loss is not None else None,
            "gain_loss_percent": str(gain_loss_percent) if gain_loss_percent is not None else None,
            "broker": holding.broker.value if holding.broker else "unknown",
        }

    async def _get_portfolio_summary(self) -> dict:
        """Get portfolio summary by calculating from holdings"""
        db = self.db_factory()
        try:
            holdings = db.query(Holding).all()

            total_value = Decimal(0)
            total_cost = Decimal(0)
            total_gain_loss = Decimal(0)

            for holding in holdings:
                total_cost += holding.total_cost or Decimal(0)
                total_value += holding.current_value or Decimal(0)
                total_gain_loss += holding.gain_loss or Decimal(0)

            total_gain_loss_percent = (
                (total_gain_loss / total_cost * 100) if total_cost > 0 else Decimal(0)
            )

            return {
                "total_value": float(total_value),
                "total_cost": float(total_cost),
                "total_gain_loss": float(total_gain_loss),
                "total_gain_loss_percent": float(total_gain_loss_percent),
                "cash_value": 0.0,
                "currency": "USD",
                "valuation_status": "complete",
                "unpriced_holdings": 0,
            }
        except Exception as e:
            logger.error(f"[Tools] Error in get_portfolio_summary: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def _get_all_holdings(self) -> dict:
        """Get all holdings"""
        db = self.db_factory()
        try:
            holdings_list = db.query(Holding).all()
            holdings = [self._holding_to_dict(h) for h in holdings_list]
            logger.info(f"[Tools] get_all_holdings() returned {len(holdings)} holdings")
            return {"holdings": holdings}
        except Exception as e:
            logger.error(f"[Tools] Error in get_all_holdings: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def _get_max_holding(self, key: str = "current_value") -> dict:
        """Get holding with maximum value"""
        db = self.db_factory()
        try:
            holdings_list = db.query(Holding).all()
            if not holdings_list:
                return {"error": "No holdings found"}

            max_holding = max(
                holdings_list,
                key=lambda h: float(getattr(h, key, 0) or 0)
            )
            result = self._holding_to_dict(max_holding)
            logger.info(f"[Tools] get_max_holding(key={key}) returned {result.get('symbol')}")
            return result
        except Exception as e:
            logger.error(f"[Tools] Error in get_max_holding: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def _get_min_holding(self, key: str = "current_value") -> dict:
        """Get holding with minimum value"""
        db = self.db_factory()
        try:
            holdings_list = db.query(Holding).all()
            if not holdings_list:
                return {"error": "No holdings found"}

            min_holding = min(
                holdings_list,
                key=lambda h: float(getattr(h, key, 0) or 0)
            )
            result = self._holding_to_dict(min_holding)
            logger.info(f"[Tools] get_min_holding(key={key}) returned {result.get('symbol')}")
            return result
        except Exception as e:
            logger.error(f"[Tools] Error in get_min_holding: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def _get_recent_transactions(self, days: int = 30) -> dict:
        """Get recent transactions"""
        from datetime import datetime, timedelta

        db = self.db_factory()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            transactions_list = db.query(Transaction).filter(
                Transaction.transaction_date >= cutoff_date
            ).all()

            transactions = [
                {
                    "id": t.id,
                    "type": str(t.transaction_type),
                    "symbol": t.asset.symbol if t.asset else "unknown",
                    "quantity": str(t.quantity),
                    "price": str(t.price),
                    "date": t.transaction_date.isoformat() if t.transaction_date else None,
                }
                for t in transactions_list
            ]
            logger.info(f"[Tools] get_recent_transactions(days={days}) returned {len(transactions)} transactions")
            return {"transactions": transactions}
        except Exception as e:
            logger.error(f"[Tools] Error in get_recent_transactions: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def call_tool(self, tool_name: str, parameters: dict = None) -> dict:
        """Call a tool by name with parameters"""
        if parameters is None:
            parameters = {}

        logger.info(f"[Tools] Calling tool: {tool_name} with params: {parameters}")

        if tool_name not in self._tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = await self._tools[tool_name](**parameters)
            logger.info(f"[Tools] Tool {tool_name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"[Tools] Error calling tool {tool_name}: {e}")
            return {"error": str(e)}

    def get_client(self):
        """Get a client interface for calling tools"""
        return PortfolioToolsClient(self)


class PortfolioToolsClient:
    """Client for calling portfolio tools"""

    def __init__(self, service: PortfolioToolsService):
        """Initialize client with service reference"""
        self.service = service
        logger.info("PortfolioToolsClient initialized")

    async def call_tool(self, tool_name: str, parameters: dict = None) -> dict:
        """Call a tool through the service"""
        return await self.service.call_tool(tool_name, parameters or {})
