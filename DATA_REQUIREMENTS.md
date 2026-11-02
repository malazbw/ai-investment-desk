# Data Requirements for AI Investment Desk

## 1️⃣ BROKER DATA (What We Pull From APIs)

### From Scalable Capital (Stocks/ETFs)
```
Holdings:
├── Symbol (e.g., "AAPL")
├── ISIN (e.g., "US0378331005")
├── Name (e.g., "Apple Inc")
├── Quantity owned
├── Purchase price (average cost basis)
├── Purchase date(s)
├── Current market price
├── Currency (EUR, USD, etc)
└── Broker fees/commissions

Transactions:
├── Symbol
├── Transaction type (BUY, SELL, DIVIDEND)
├── Quantity
├── Price per unit
├── Transaction date
├── Settlement date
├── Commission/fees
├── Broker transaction ID
└── Notes
```

### From Binance (Cryptocurrency)
```
Holdings:
├── Symbol (e.g., "BTC", "ETH")
├── Name (e.g., "Bitcoin")
├── Quantity owned
├── Average purchase price
├── Current market price
├── Purchase date(s)
├── Trading pair (BTC/USDT, etc)
├── Exchange fees
└── Staking rewards (if any)

Transactions:
├── Symbol
├── Type (BUY, SELL, TRANSFER, STAKING_REWARD, FEE)
├── Quantity
├── Price
├── Date
├── Fee amount
├── Fee currency
├── Wallet address (if transfer)
└── Transaction hash
```

---

## 2️⃣ CALCULATED DATA (What We Store)

### Holdings with Calculations
```
For each holding:
├── Total cost basis (quantity × average price)
├── Current total value (quantity × current price)
├── Unrealized gain/loss (current value - cost basis)
├── Unrealized gain/loss % 
├── Holding period (days held)
└── Annual return %
```

### Portfolio-Level Metrics
```
Daily:
├── Total portfolio value (sum of all holdings)
├── Total cost basis (sum of all purchases)
├── Total unrealized gain/loss
├── Unrealized gain/loss %
├── Portfolio allocation % (each asset as % of total)
├── Asset class breakdown (stocks %, ETFs %, crypto %)
├── Currency exposure (EUR %, USD %, etc)
├── Cash balance
└── Timestamp

Historical:
├── Daily snapshots (for trend analysis)
├── Monthly returns
├── Year-to-date return
└── All-time return
```

### Risk Metrics
```
├── Portfolio volatility
├── Sharpe ratio
├── Max drawdown
├── Correlation between assets
├── VaR (Value at Risk)
└── Sector concentration
```

---

## 3️⃣ MARKET DATA (What We Need from External Sources)

### Price History
```
For each asset:
├── Current price
├── Open/High/Low/Close (OHLC) - daily
├── 52-week high/low
├── Price change % (1d, 1w, 1m, 3m, 1y)
└── Trading volume

Update frequency:
├── Stocks: Daily at market close
├── Crypto: Real-time or hourly
└── Historical: As needed for analysis
```

### Asset Master Data
```
├── Symbol
├── Full name
├── Asset type (STOCK, ETF, CRYPTO, COMMODITY)
├── Currency
├── Exchange
├── Sector (if stock)
├── Industry (if stock)
├── Market cap
├── P/E ratio
└── Dividend yield
```

---

## 4️⃣ TAX & REPORTING DATA (For Tax Season)

### Per Transaction
```
├── Acquisition date
├── Sale date (if sold)
├── Holding period (long-term vs short-term)
├── Cost basis
├── Sale proceeds
├── Realized gain/loss
├── Fees
└── Tax lot (for cost basis method)
```

### Annual Summary
```
├── Total realized gains
├── Total realized losses
├── Total dividends received
├── Total interest earned
├── Total fees paid
├── Currency gains/losses (if multi-currency)
└── Wash sale violations
```

---

## 5️⃣ NEWS & INTELLIGENCE DATA (Future - Phase 2)

```
For each holding:
├── Recent news articles
├── Earnings announcements
├── Dividend announcements
├── Stock split announcements
├── Analyst ratings
├── Price targets
└── Sentiment score
```

---

## 6️⃣ AI ASSISTANT DATA (Future - Phase 3)

```
Context the LLM needs:
├── Your entire portfolio composition
├── Each holding's performance
├── Your investment goals
├── Risk tolerance
├── Time horizon
├── Historical decisions
├── Market conditions
└── Recommendations history
```

---

## 📊 Current Database Schema (What We Have)

```sql
assets
├── id (symbol)
├── symbol
├── name
├── asset_type (STOCK, ETF, CRYPTO, etc)
├── isin
├── currency
├── created_at
└── updated_at

holdings
├── id
├── asset_id (FK → assets)
├── broker (SCALABLE_CAPITAL or BINANCE)
├── quantity
├── average_cost
├── total_cost
├── current_price
├── current_value
├── created_at
└── updated_at

transactions
├── id
├── asset_id (FK → assets)
├── broker
├── transaction_type (BUY, SELL, DIVIDEND)
├── quantity
├── price
├── total_amount
├── commission
├── transaction_date
├── settlement_date
├── broker_transaction_id
├── notes
└── created_at

prices
├── id
├── asset_id (FK → assets)
├── price
├── price_date
├── source
└── created_at

portfolio_snapshots
├── id
├── snapshot_date
├── total_value
├── total_cost
├── total_gain_loss
├── total_gain_loss_percent
├── cash_value
└── created_at
```

---

## 🎯 Which Data Do We Need FIRST?

### Phase 1B: Broker Integration (NEXT - 1-2 weeks)
```
MUST HAVE:
✅ Holdings (quantity, price, dates)
✅ Transactions (buys, sells)
✅ Current prices
✅ Cost basis calculations
✅ Portfolio summary metrics

NICE TO HAVE:
⏳ Historical prices
⏳ ISIN/security identifiers
⏳ Sector classification
```

### Phase 2: Market Intelligence (2-3 weeks later)
```
NEW DATA NEEDED:
├── Real-time price updates
├── Historical OHLC data
├── News feeds
├── Economic indicators
└── Analyst ratings
```

### Phase 3: AI Assistant (1 month later)
```
NEW DATA NEEDED:
├── Your investment goals (text)
├── Risk tolerance (questionnaire)
├── Time horizon
├── Historical preferences
└── Recommendation scoring
```

### Phase 4: Trading Automation (2 months later)
```
NEW DATA NEEDED:
├── Strategy parameters
├── Backtest results
├── Risk limits per trade
├── Maximum position sizes
└── Daily loss caps
```

---

## ❓ Questions for You

To prioritize what we build first, I need to know:

1. **Scalable Capital or Binance first?**
   - Stocks/ETFs? → Scalable Capital
   - Crypto? → Binance
   - Both at once? → Both

2. **What metrics matter most to you?**
   - Portfolio value & gains/losses?
   - Individual asset performance?
   - Risk analysis?
   - Tax reporting?
   - All of the above?

3. **How often do you want data updated?**
   - Daily at market close?
   - Real-time throughout the day?
   - Weekly?
   - Manual sync on demand?

4. **Do you need historical data?**
   - Just current holdings?
   - Last 1 year?
   - Last 5 years?
   - All-time?

5. **Multi-currency support?**
   - Just EUR?
   - EUR + USD?
   - Multiple currencies?

---

**What are your priorities?** This will tell us exactly what to build in Phase 1B! 🎯
