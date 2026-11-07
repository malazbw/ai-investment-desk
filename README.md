# AI Investment Desk

AI Investment Desk is a personal finance app for keeping your investment
portfolio information in one place and exploring it through a dashboard and an
AI-assisted chat. It brings together the holdings and transactions you record,
prices and research data you import, and summaries that help you understand
what is currently stored about your portfolio.

It is a portfolio tracking and research tool—not a bank, broker, or automated
trading system. It does not connect to your accounts to trade or place orders.
The quality of its analysis depends on the accuracy and freshness of the data
you provide or import.

## What can you do with it?

- **See your portfolio at a glance:** review the recorded holdings, portfolio
  value, costs, and gains or losses.
- **Review your investments:** look up holdings and transaction history, and
  save portfolio snapshots to compare over time.
- **Ask questions in chat:** ask about the portfolio information in the app.
  The app gathers relevant stored data and an AI model turns it into a readable
  answer.
- **Explore valuation information:** review stored prices and available company
  financial facts for supported investments.
- **Add or test portfolio data:** record transactions through the API or load
  sample holdings using the virtual broker.
- **Add research context:** import available company news, economic indicators,
  financial facts, prices, and foreign-exchange rates using the documented API
  endpoints.

The app does not guarantee that data is current. Chat questions mainly use
information already stored in the database; asking a question does not
automatically refresh all data sources.

## A simple example

1. Start the app and open its dashboard or API documentation.
2. Add portfolio information, or load the sample portfolio to explore the app.
3. Import any optional research data you want to use.
4. Ask a portfolio question in chat, such as “What holdings are recorded in my
   portfolio?”
5. Review the answer alongside the data and its source dates in the app.

The sample portfolio and its prices are for testing only; they are not live
market data.

## How the AI and agents work

When a user sends a chat message:

1. The app uses simple keyword and ticker matching to choose which available
   specialists should handle the question. This routing is rule-based, not
   performed by an AI model.
2. The selected specialists read relevant information from the app's database
   and return structured results.
3. The app combines those results and sends them, along with the question, to
   the configured language model (LLM).
4. The LLM writes a natural-language answer based on the information it was
   given.

Currently, chat registers the **portfolio** and **valuation** agents. Code for
market-research, macro-context, and risk agents also exists, but those agents
are not currently registered with the chat endpoint. The AI does not directly
read the database, make trades, or guarantee that its answer is correct.

The app supports **Gemini**, **Claude**, and **Ollama** (a model served locally).
Which one is used depends on the `LLM_PROVIDER` setting. Hosted providers need
their own API key; Ollama needs its local service running.

## What data does it use?

### Your portfolio

The app stores assets, holdings, transactions, prices, and historical portfolio
snapshots in its database. It can use SQLite for local development or
PostgreSQL. You can enter data through the API; the virtual broker supplies
example data for testing.

### Optional research sources

These sources require setup and may not be enabled in every installation:

| Source | Example data | Notes |
| --- | --- | --- |
| FRED | VIX, US interest rates, Treasury yields, and CPI | Imported economic observations; requires `FRED_API_KEY` |
| SEC EDGAR | Company-reported financial facts | Requires an identifying `SEC_USER_AGENT` contact email |
| NewsAPI | Company-news headlines and publisher descriptions | Uses headlines/snippets, not full article text; requires `NEWSAPI_KEY` |
| eToro | Market quotes for supported instruments | Requires `ETORO_API_KEY` and `ETORO_USER_KEY` |
| Frankfurter | EUR reference rates against USD, GBP, and CHF | Used for stored exchange-rate data |

Imported economic, financial, and news data can be delayed or incomplete.
`SETUP.md` describes the API endpoints for importing data and the required
settings.

## Run locally

Requirements: Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
python run.py
```

The API is available at <http://localhost:8000>. Interactive API documentation
is at <http://localhost:8000/docs>. Configure optional credentials in a local
`.env` file. Never commit that file or put real credentials in this README.

To load sample portfolio data:

```bash
curl -X POST http://localhost:8000/api/portfolio/sync/virtual
```

For detailed setup and data-import instructions, see [SETUP.md](SETUP.md).
