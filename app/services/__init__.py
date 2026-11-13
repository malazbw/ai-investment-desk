"""Services package - business logic for portfolio and market data"""
# Import from old services.py (temporary compatibility)
import sys
import importlib.util

spec = importlib.util.spec_from_file_location("_services", "/Users/hala.al.kuwatly/projects/ai-investment-desk/app/services.py")
_services_module = importlib.util.module_from_spec(spec)
sys.modules['_services'] = _services_module
spec.loader.exec_module(_services_module)

# Re-export old services
EtoroPriceService = _services_module.EtoroPriceService
MacroDataService = _services_module.MacroDataService
PortfolioService = _services_module.PortfolioService
SECFundamentalsService = _services_module.SECFundamentalsService
ExchangeRateService = _services_module.ExchangeRateService
NewsService = _services_module.NewsService

# Import new services
from app.services.yahoo_finance import YahooFinanceService, YahooFinanceNews

__all__ = [
    "EtoroPriceService",
    "MacroDataService",
    "PortfolioService",
    "SECFundamentalsService",
    "ExchangeRateService",
    "NewsService",
    "YahooFinanceService",
    "YahooFinanceNews",
]
