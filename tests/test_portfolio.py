"""
Integration tests for portfolio API
"""
import pytest
from decimal import Decimal
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app import routes
from app.models import Base, BrokerType, AssetType, TransactionType
from app.services import PortfolioService
from app.llm.client import LLMClient


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def clean_db():
    """Provide a clean database for testing"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health_check():
    """Test basic health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"]


def test_sync_virtual_broker(clean_db):
    """Test loading virtual broker data"""
    response = client.post("/api/portfolio/sync/virtual")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "synced"
    assert data["holdings_loaded"] == 3
    assert data["transactions_loaded"] == 2

    second_response = client.post("/api/portfolio/sync/virtual")
    assert second_response.status_code == 200
    assert second_response.json()["transactions_loaded"] == 0
    assert len(client.get("/api/portfolio/transactions").json()) == 2


def test_portfolio_summary(clean_db):
    """Test portfolio summary after sync"""
    client.post("/api/portfolio/sync/virtual")
    response = client.get("/api/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["holdings_count"] == 3
    assert data["currency"] == "USD"
    assert data["valuation_status"] == "complete"
    assert Decimal(str(data["total_gain_loss"])) == Decimal("2021.2500")


def test_get_holdings(clean_db):
    """Test retrieving holdings"""
    client.post("/api/portfolio/sync/virtual")
    response = client.get("/api/portfolio/holdings")
    assert response.status_code == 200
    holdings = response.json()
    assert len(holdings) == 3
    assert all(holding["price_source"] == "virtual_broker" for holding in holdings)
    assert all(holding["price_currency"] == "USD" for holding in holdings)
    assert all(holding["price_freshness"] == "fresh" for holding in holdings)


def test_get_transactions(clean_db):
    """Test retrieving transactions"""
    client.post("/api/portfolio/sync/virtual")
    response = client.get("/api/portfolio/transactions")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_empty_portfolio(clean_db):
    """Test empty portfolio summary"""
    response = client.get("/api/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["holdings_count"] == 0
    assert data["valuation_status"] == "empty"


def test_mixed_currency_summary_does_not_add_incomparable_values(clean_db):
    from app.models import Asset, Holding, Price

    db = TestingSessionLocal()
    try:
        for symbol, currency, value in (
            ("AAA", "EUR", Decimal("100")),
            ("BBB", "USD", Decimal("200")),
        ):
            db.add(Asset(
                id=symbol,
                symbol=symbol,
                name=symbol,
                asset_type=AssetType.STOCK,
                currency=currency,
            ))
            db.flush()
            db.add(Holding(
                asset_id=symbol,
                broker=BrokerType.SCALABLE_CAPITAL,
                quantity=Decimal("1"),
                average_cost=value,
                total_cost=value,
                current_price=value,
                current_value=value,
            ))
            db.add(Price(
                asset_id=symbol,
                price=value,
                price_date=datetime.utcnow(),
                source="test",
                currency=currency,
            ))
        db.commit()
    finally:
        db.close()

    response = client.get("/api/portfolio/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["valuation_status"] == "mixed_currency"
    assert summary["currency"] is None
    assert summary["total_value"] is None
    assert summary["total_gain_loss"] is None


def test_data_status_reports_unsynced_sources(clean_db):
    response = client.get("/api/portfolio/data-status")
    assert response.status_code == 200
    assert response.json()["prices"]["status"] == "not_synced"
    assert response.json()["fundamentals"]["status"] == "not_synced"


def test_transaction_rejects_sell_quantity_above_holding(clean_db):
    client.post("/api/portfolio/sync/virtual")
    response = client.post(
        "/api/portfolio/transactions",
        json={
            "asset_id": "AAPL",
            "broker": "scalable_capital",
            "transaction_type": "sell",
            "quantity": "11",
            "price": "175.50",
            "total_amount": "1930.50",
            "commission": "0",
            "transaction_date": datetime.utcnow().isoformat(),
        },
    )
    assert response.status_code == 400
    assert "Cannot sell more units" in response.json()["detail"]


def test_chat_analysis_does_not_change_portfolio(clean_db, monkeypatch):
    class FakeProvider:
        def __init__(self):
            self.calls = []

        async def analyze(self, user_message, system_prompt, context):
            self.calls.append(system_prompt)
            if "Select only the specialists needed" in system_prompt:
                return '["portfolio"]'
            return "The answer is based on stored portfolio data."

    provider = FakeProvider()
    monkeypatch.setattr(routes, "llm_client", LLMClient(provider))
    monkeypatch.setattr(routes, "get_session_factory", lambda: TestingSessionLocal)
    client.post("/api/portfolio/sync/virtual")
    before = len(client.get("/api/portfolio/transactions").json())

    response = client.post(
        "/api/chat/message",
        json={"message": "What are my holdings?"},
    )

    assert response.status_code == 200
    assert "AAPL: 10 units" in response.json()["response"]
    assert "MSFT: 5 units" in response.json()["response"]
    assert "VOO: 20 units" in response.json()["response"]
    assert "sample data, not live quotes" in response.json()["response"]
    assert response.json()["agents_used"] == ["portfolio"]
    assert len(provider.calls) == 1
    assert len(client.get("/api/portfolio/transactions").json()) == before
