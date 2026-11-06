"""
Financial data fetcher - get earnings, P/E, valuation metrics
Uses yfinance for simplicity and reliability
"""
import yfinance as yf
from typing import Dict, Optional, List
from decimal import Decimal
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FinancialFetcher:
    """Fetch company financial data including earnings and valuation metrics"""

    @staticmethod
    def get_stock_info(ticker: str) -> Dict:
        """
        Get comprehensive stock info including valuation metrics.
        Returns: P/E ratio, market cap, earnings, etc.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            financials = {
                "ticker": ticker,
                "fetched_at": datetime.utcnow().isoformat(),
                "price": info.get("currentPrice"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "eps": info.get("trailingEps"),
                "dividend_yield": info.get("dividendYield"),
                "profit_margin": info.get("profitMargins"),
                "revenue": info.get("totalRevenue"),
                "debt_to_equity": info.get("debtToEquity"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
            }

            logger.info(f"Fetched financials for {ticker}")
            return {k: v for k, v in financials.items() if v is not None}

        except Exception as e:
            logger.error(f"Error fetching financials for {ticker}: {e}")
            return {"ticker": ticker, "error": str(e)}

    @staticmethod
    def get_valuation(ticker: str) -> Dict:
        """Get valuation metrics: P/E, P/B, PEG, etc."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                "ticker": ticker,
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "peg_ratio": info.get("pegRatio"),
                "forward_pe": info.get("forwardPE"),
                "fetched_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error fetching valuation for {ticker}: {e}")
            return {"ticker": ticker, "error": str(e)}

    @staticmethod
    def get_earnings_history(ticker: str) -> Dict:
        """Get historical earnings data"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                "ticker": ticker,
                "eps_trailing": info.get("trailingEps"),
                "eps_forward": info.get("forwardEps"),
                "earnings_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenuePerShare"),
                "fetched_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error fetching earnings history for {ticker}: {e}")
            return {"ticker": ticker, "error": str(e)}

    @staticmethod
    def batch_fetch_valuations(tickers: List[str]) -> Dict[str, Dict]:
        """Fetch valuations for multiple tickers"""
        results = {}
        for ticker in tickers:
            valuation = FinancialFetcher.get_valuation(ticker)
            if "error" not in valuation:
                results[ticker] = valuation
        return results

    @staticmethod
    def compare_valuations(tickers: List[str]) -> Dict:
        """Compare valuations across multiple stocks"""
        valuations = FinancialFetcher.batch_fetch_valuations(tickers)

        # Calculate averages for comparison
        pe_ratios = [v.get("pe_ratio") for v in valuations.values() if v.get("pe_ratio")]
        pb_ratios = [v.get("pb_ratio") for v in valuations.values() if v.get("pb_ratio")]

        comparison = {
            "stocks_analyzed": len(valuations),
            "average_pe": sum(pe_ratios) / len(pe_ratios) if pe_ratios else None,
            "average_pb": sum(pb_ratios) / len(pb_ratios) if pb_ratios else None,
            "valuations_by_stock": valuations,
        }

        return comparison
