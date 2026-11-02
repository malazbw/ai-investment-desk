# Data Pipeline Design for AI Investment Desk

## 📊 Data Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                            │
├─────────────────────────────────────────────────────────────┤
│  eToro API        │  yfinance    │  CoinGecko  │  FRED API  │
│  (Verified soon)  │  (Stocks)    │  (Crypto)   │  (Macro)   │
└────────┬──────────┴──────┬───────┴──────┬──────┴──────┬─────┘
         │                 │              │             │
         └─────────────────┼──────────────┼─────────────┘
                           ↓
         ┌──────────────────────────────────────┐
         │    Data Fetcher (Python Scripts)     │
         │  - Scheduled jobs (APScheduler)      │
         │  - Fetch from multiple sources       │
         │  - Handle errors & retries           │
         └──────────────────┬───────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │   Data Validation & Normalization    │
         │  - Check data quality                │
         │  - Convert to standard format        │
         │  - Remove duplicates                 │
         └──────────────────┬───────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │     PostgreSQL Database              │
         │  - prices table                      │
         │  - assets table                      │
         │  - snapshots table                   │
         │  - metrics table                     │
         └──────────────────┬───────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │    Analytics Engine (Python)         │
         │  - Calculate metrics                 │
         │  - Generate insights                 │
         │  - Score opportunities               │
         └──────────────────┬───────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │      FastAPI REST Endpoints          │
         │  - /prices                           │
         │  - /portfolio/metrics                │
         │  - /analysis/opportunities           │
         │  - /insights                         │
         └──────────────────┬───────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │    Frontend Dashboard                │
         │  - Display metrics                   │
         │  - Show charts                       │
         │  - AI recommendations                │
         └──────────────────────────────────────┘
```

---

## 1️⃣ STOCK DATA PIPELINE

### **Data Sources**

```
PRIMARY (eToro API - when verified):
├── Real-time stock prices
├── Historical daily data (OHLC)
├── Market hours & trading volume
├── All listed stocks & ETFs
└── Endpoint: GET /api/v1/quotes/{symbol}

FALLBACK (yfinance - free):
├── All US stocks, ETFs, indices
├── Complete historical data (years back)
├── Free, no authentication needed
└── pip install yfinance
```

### **Data to Store**

```sql
TABLE: stock_prices
├── id (primary key)
├── symbol (AAPL, MSFT, etc)
├── date (2024-10-31)
├── open (price at market open)
├── high (daily high)
├── low (daily low)
├── close (price at market close)
├── volume (shares traded)
├── source (etoro or yfinance)
└── created_at (when we fetched it)

TABLE: stock_assets (master data)
├── id
├── symbol
├── name (Apple Inc)
├── sector (Technology)
├── industry (Consumer Electronics)
├── market_cap
├── pe_ratio
├── dividend_yield
└── updated_at
```

### **Update Frequency**

```
REAL-TIME (During market hours):
├── Every 5 minutes
├── Only if trading (9:30 AM - 4 PM ET)
├── Source: eToro API (if available)

DAILY (After market close):
├── 4:30 PM ET (when market closes)
├── Fetch full day's OHLCV data
├── Source: yfinance (reliable fallback)
├── Run time: ~5 minutes

WEEKLY:
├── Calculate technical indicators
├── Update fundamental data (P/E, sector, etc)
├── Recalculate correlations

MONTHLY:
├── Update master data (company info)
├── Earnings announcements
├── Dividend updates
```

### **ETL Process**

```python
Job: fetch_stock_prices()
Run: Daily 4:35 PM ET

Steps:
1. Get list of stocks we track
2. Fetch latest price for each:
   - Try eToro API first
   - Fallback to yfinance
3. Validate data:
   - Price > 0
   - Date is today
   - OHLC makes sense (high >= low >= close)
4. Store in database
5. Calculate daily metrics:
   - Daily return %
   - Price change
   - Volume trend
6. Log results
```

---

## 2️⃣ CRYPTO DATA PIPELINE

### **Data Sources**

```
PRIMARY (CoinGecko - free, no auth):
├── Real-time crypto prices
├── All cryptocurrencies
├── Historical data
├── Market cap, volume
├── No rate limits for free tier
└── https://api.coingecko.com/api/v1/

SECONDARY (Binance API - if you trade there):
├── Real-time prices
├── Order book data
├── Historical trades
└── Free public endpoints

TERTIARY (eToro API - when verified):
├── If eToro supports crypto
└── Real-time prices
```

### **Data to Store**

```sql
TABLE: crypto_prices
├── id
├── symbol (BTC, ETH, SOL, etc)
├── coin_id (bitcoin, ethereum - for CoinGecko)
├── date
├── price_usd
├── price_eur (if multi-currency)
├── market_cap
├── volume_24h
├── price_change_24h %
├── price_change_7d %
├── source (coingecko, binance, etoro)
└── created_at

TABLE: crypto_assets (master data)
├── id
├── symbol
├── name (Bitcoin)
├── coin_id
├── description
├── market_cap_rank
├── market_cap
├── total_supply
├── circulating_supply
└── updated_at
```

### **Update Frequency**

```
REAL-TIME (24/7):
├── Every 1 hour (crypto never sleeps)
├── Source: CoinGecko API
├── Process: ~30 seconds per run

HOURLY AGGREGATES:
├── Calculate 24h metrics
├── Update market dominance
├── Track volume changes

DAILY CALCULATIONS:
├── Daily returns
├── 7-day performance
├── 30-day volatility
└── Run time: ~2 AM UTC (off-hours)

WEEKLY:
├── Correlation with other cryptos
├── Trend analysis
└── On-chain metrics (if available)
```

### **ETL Process**

```python
Job: fetch_crypto_prices()
Run: Hourly (every 60 minutes)

Steps:
1. Get list of cryptos we track
2. Fetch from CoinGecko:
   - Current price (USD, EUR if needed)
   - Market cap
   - Volume
   - Price changes (24h, 7d, 30d)
3. Validate:
   - Price > 0
   - Market cap makes sense
   - Volume < market cap
4. Store in database
5. Calculate metrics:
   - Hourly return %
   - Change from yesterday
   - Market cap rank
6. Detect anomalies:
   - Price spike > 10%?
   - Volume spike > 2x?
```

---

## 3️⃣ PORTFOLIO SNAPSHOT PIPELINE

### **Data Sources**

```
DUMMY DATA (For now):
├── Hardcoded holdings
├── AAPL: 100 shares
├── MSFT: 50 shares
├── BTC: 0.5
├── ETH: 2.0
└── Updated manually or from CSV

REAL DATA (Later - eToro API):
├── Your actual holdings
├── Quantities and cost basis
├── Purchase dates
└── Current portfolio value
```

### **Data to Store**

```sql
TABLE: dummy_holdings (temporary)
├── id
├── symbol (AAPL, BTC, etc)
├── quantity (100, 0.5, etc)
├── purchase_price (avg cost basis)
├── purchase_date (when bought)
└── asset_type (stock, crypto, etf)

TABLE: portfolio_snapshots (daily)
├── id
├── snapshot_date (2024-10-31)
├── total_value (calculated)
├── total_cost (sum of cost basis)
├── total_gain_loss (value - cost)
├── total_return % (gain / cost * 100)
├── by_asset (JSON with per-holding breakdown)
└── created_at
```

### **Update Frequency**

```
DAILY (After market close):
├── 4:35 PM ET
├── Calculate portfolio metrics
├── Store snapshot
├── Detect changes

INTRADAY (Optional - for real-time dashboard):
├── Every 5 minutes during market hours
├── Lightweight calculation
├── No database write
├── Just in-memory cache
```

### **Calculation Process**

```python
Job: calculate_portfolio_metrics()
Run: Daily 4:35 PM ET

For each holding:
  current_value = quantity * current_price
  gain_loss = current_value - (quantity * purchase_price)
  return % = gain_loss / (quantity * purchase_price) * 100

Portfolio totals:
  total_value = sum(current_value)
  total_cost = sum(quantity * purchase_price)
  total_gain_loss = total_value - total_cost
  total_return % = total_gain_loss / total_cost * 100
  
Store everything
```

---

## 4️⃣ CALCULATED METRICS PIPELINE

### **Metrics to Calculate**

```
PERFORMANCE METRICS:
├── Daily return %
├── Weekly return %
├── Monthly return %
├── YTD return %
├── All-time return %
├── Annualized return %
└── Return vs benchmark

RISK METRICS:
├── Daily volatility
├── 30-day volatility (annualized)
├── Maximum drawdown (peak to trough)
├── Sharpe ratio (risk-adjusted returns)
├── Beta (correlation with S&P 500)
├── Value at Risk (5% worst case)
└── Correlation matrix (between holdings)

EFFICIENCY METRICS:
├── Win rate (days with positive returns)
├── Sharpe ratio
├── Sortino ratio
├── Calmar ratio
└── Information ratio

HOLDINGS METRICS:
├── Per-holding return %
├── Per-holding volatility
├── Contribution to portfolio
├── Concentration risk
└── Diversification score
```

### **Data to Store**

```sql
TABLE: portfolio_metrics (daily)
├── date
├── daily_return %
├── daily_volatility
├── 30day_volatility
├── ytd_return %
├── all_time_return %
├── max_drawdown
├── sharpe_ratio
├── drawdown_days_since_recovery
└── created_at

TABLE: asset_metrics (daily, per holding)
├── date
├── symbol
├── daily_return %
├── 30day_return %
├── ytd_return %
├── volatility
├── contribution_to_portfolio %
└── created_at
```

### **Update Frequency**

```
REAL-TIME (Dashboard):
├── Calculate using cached prices
├── No database query
├── Every 5 minutes

DAILY:
├── After market close (4:35 PM)
├── Store in database
├── Calculate all metrics

WEEKLY:
├── Calculate correlation matrix
├── Rebalance analysis
├── On Monday morning

MONTHLY:
├── Long-term trend analysis
├── Composite metrics
├── On 1st of month
```

---

## 5️⃣ MACROECONOMIC DATA PIPELINE

### **Data Sources**

```
MACRO INDICATORS (FRED API - free):
├── Interest rates (Fed funds rate)
├── Inflation (CPI)
├── GDP growth
├── Unemployment
├── VIX (market volatility)
└── https://fred.stlouisfed.org/

MARKET DATA:
├── S&P 500 index price
├── Russell 2000
├── Nasdaq 100
├── Bond yields (10-year, 2-year)
└── Dollar index
```

### **Data to Store**

```sql
TABLE: macro_indicators (daily)
├── date
├── fed_funds_rate
├── inflation_rate
├── unemployment_rate
├── vix_index
├── sp500_price
├── sp500_return %
├── yield_10yr
├── yield_2yr
└── created_at
```

### **Update Frequency**

```
DAILY (Close of business):
├── Market indices (S&P 500, VIX)
├── Yields
├── Source: yfinance

WEEKLY:
├── Economic indicators
├── Source: FRED API

MONTHLY:
├── Official releases
├── Inflation, unemployment
├── Government reports
```

---

## 📅 COMPLETE SCHEDULE

### **Every 1 Hour (24/7)**
```
fetch_crypto_prices()
  └─ Get latest crypto prices from CoinGecko
  └─ Store in database
  └─ Calculate crypto metrics
```

### **Daily at 4:35 PM ET (Market Close)**
```
fetch_stock_prices()
  └─ Get daily OHLCV for all stocks
  └─ Store in database
  
calculate_portfolio_metrics()
  └─ Calculate daily performance
  └─ Store portfolio snapshot
  └─ Calculate returns, volatility
  
calculate_asset_metrics()
  └─ Per-holding performance
  └─ Risk metrics
  └─ Contribution analysis
```

### **Daily at 2:00 AM UTC (Off-hours)**
```
calculate_correlations()
  └─ Recalculate correlation matrix
  └─ Detect diversification issues
  
generate_insights()
  └─ Identify opportunities
  └─ Flag warnings
  └─ Generate AI recommendations
```

### **Weekly (Monday 9:00 AM)**
```
analyze_market_regime()
  └─ Bull or bear market?
  └─ Volatility environment?
  
rebalancing_check()
  └─ Has allocation drifted?
  └─ Recommend rebalancing?
```

### **Monthly (1st of month, 8:00 AM)**
```
generate_monthly_report()
  └─ Performance summary
  └─ Risk analysis
  └─ Tax implications
  
macro_analysis()
  └─ Economic conditions
  └─ Market outlook
  └─ Asset class performance
```

---

## 🏗️ Database Schema Summary

```sql
-- Assets master data
CREATE TABLE stock_assets (id, symbol, name, sector, market_cap, pe_ratio, ...);
CREATE TABLE crypto_assets (id, symbol, name, market_cap_rank, ...);

-- Price history
CREATE TABLE stock_prices (id, symbol, date, open, high, low, close, volume, source, ...);
CREATE TABLE crypto_prices (id, symbol, date, price_usd, market_cap, volume_24h, ...);

-- Portfolio data
CREATE TABLE dummy_holdings (id, symbol, quantity, purchase_price, purchase_date, ...);
CREATE TABLE portfolio_snapshots (date, total_value, total_cost, total_return%, ...);

-- Metrics
CREATE TABLE portfolio_metrics (date, daily_return%, volatility, sharpe_ratio, ...);
CREATE TABLE asset_metrics (date, symbol, return%, volatility, contribution%, ...);

-- Macro data
CREATE TABLE macro_indicators (date, fed_funds_rate, inflation, vix, sp500_price, ...);
```

---

## 🎯 MVP (What to Build First)

### **Phase 1: Basic Data Pipeline (Week 1)**
```
✅ Set up data fetcher for stock prices (yfinance)
✅ Set up data fetcher for crypto prices (CoinGecko)
✅ Create database schema
✅ Store daily snapshots
✅ Calculate basic metrics (daily return %, volatility)
```

### **Phase 2: Add eToro Integration (Week 2)**
```
📋 Integrate eToro API (when account verified)
📋 Pull real portfolio data
📋 Replace dummy holdings
```

### **Phase 3: Enhanced Analytics (Week 3)**
```
📋 Add macroeconomic indicators
📋 Calculate correlations
📋 Generate insights
📋 Add AI recommendations
```

### **Phase 4: Dashboard & AI (Week 4)**
```
📋 Create analytics API endpoints
📋 Build dashboard UI
📋 Wire up Claude AI for insights
```

---

## ✅ Questions to Confirm

1. **Frequency good?** (Hourly crypto, daily stocks, etc?)
2. **Data sources OK?** (CoinGecko, yfinance, eToro, FRED?)
3. **Metrics comprehensive?** (Missing anything?)
4. **Storage plan clear?** (PostgreSQL tables?)
5. **Schedule realistic?** (Can run as background jobs?)

**Any changes needed before we start building?** 🚀
