"""
Integration tests for portfolio API
"""
import pytest
from decimal import Decimal
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base, BrokerType, AssetType, TransactionType
from app.services import PortfolioService


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
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


def test_portfolio_summary(clean_db):
    """Test portfolio summary after sync"""
    client.post("/api/portfolio/sync/virtual")
    response = client.get("/api/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["holdings_count"] == 3


def test_get_holdings(clean_db):
    """Test retrieving holdings"""
    client.post("/api/portfolio/sync/virtual")
    response = client.get("/api/portfolio/holdings")
    assert response.status_code == 200
    holdings = response.json()
    assert len(holdings) == 3


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
