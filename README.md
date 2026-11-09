# AI Investment Desk

AI Investment Desk is a personal portfolio tracking and investment research
application. It brings together holdings you record, imported market and
research data, and an AI-assisted chat that helps explain the information stored
in your database.

It is a research and decision-support tool, not a broker or a source of
personalized financial advice. The current broker integrations are placeholders;
the app does not connect to brokerage accounts or place trades. Analysis depends
on the data you provide and its freshness.

## Screenshots

### Portfolio dashboard

Review portfolio value, data freshness, and the holdings table with each price
source.

![AI Investment Desk portfolio dashboard](screenshots/Screenshot%20from%202026-11-09%2011-18-39.png)

### AI valuation analysis

Ask about the valuation inputs stored for your holdings and review their
reported periods and sources.

![AI Investment Desk valuation analysis](screenshots/Screenshot%20from%202026-11-09%2011-19-13.png)

Screenshots are examples; their figures can become outdated and are not
investment advice or a promise of future performance.

## What it does

- **Portfolio tracking:** record holdings and transactions, review portfolio
  summaries, and save historical snapshots.
- **Research data:** import supported company facts, market prices, news,
  economic observations, and exchange rates.
- **AI-assisted analysis:** ask questions about stored portfolio and research
  data, with source dates and missing-data limitations included when available.
- **Virtual portfolio:** load sample holdings to explore the app without a
  brokerage account.

The app does not automatically refresh every source when you ask a chat
question. Refresh data through the API or wait for a configured scheduled job.
Stored and imported data can be delayed, incomplete, or unavailable.

## How chat works

The chat workflow uses LangGraph to coordinate the registered specialists:
**portfolio**, **market research**, **macro**, **risk**, and **valuation**.
Unless you choose specialists explicitly, the configured LLM selects which
specialists are relevant. Selected specialists query stored data and run in
parallel. A question handled only by the portfolio specialist can be answered
directly; other results are combined by an LLM synthesis step.

The market-research specialist can also request on-demand company research for
an explicitly mentioned ticker. Depending on configuration, this may include
SEC facts, an eToro quote, and news headlines or publisher-provided snippets.
This research does not add the company to your portfolio. Full article text is
not fetched.

Supported LLM providers are **Ollama**, **Gemini**, and **Claude**. Ollama is the
default and expects a local service at `http://localhost:11434`; Gemini and
Claude require their respective API keys. The LLM interprets specialist
results; deterministic portfolio and valuation calculations are performed by
application code.

## Data sources

| Source | Data | Configuration |
| --- | --- | --- |
| SQLite or PostgreSQL | Portfolio, transactions, prices, and research records | SQLite is the local default; set `DATABASE_URL` for PostgreSQL |
| eToro | USD quotes for supported portfolio instruments | `ETORO_API_KEY` and `ETORO_USER_KEY` |
| SEC EDGAR | Reported company facts for supported holdings | `SEC_USER_AGENT` with a contact email |
| FRED | Selected US economic indicators, including VIX, rates, and CPI | `FRED_API_KEY` |
| NewsAPI | Company-news headlines and available publisher descriptions | `NEWSAPI_KEY` |
| Frankfurter | EUR reference rates against USD, GBP, and CHF | No API key required |

The dashboard and chat identify stored price sources and dates where available.
Virtual-broker prices are examples, not live quotes. When prices are missing or
currencies differ, the portfolio summary reports incomplete or unavailable
valuation rather than presenting an unsupported complete total.

## Run locally

Requirements: Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
python run.py
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.
The development server runs at <http://localhost:8000>.

- **Dashboard:** <http://localhost:8000/static/index.html>
- **Interactive API docs:** <http://localhost:8000/docs>
- **Health check:** <http://localhost:8000/health>

The API root (`/`) returns application status information; use the static URL
above to open the dashboard.

To load the virtual portfolio:

```bash
curl -X POST http://localhost:8000/api/portfolio/sync/virtual
```

The virtual broker loads sample data and is safe to use without broker
credentials. Optional API keys and provider settings can be placed in a local
`.env` file. Do not commit real credentials.

For chat, select an LLM provider with `LLM_PROVIDER` (`ollama`, `gemini`, or
`claude`). Ollama is the default; set `OLLAMA_API_URL` and `OLLAMA_MODEL` if
your local server or model differs from the defaults. For hosted providers,
configure `GEMINI_API_KEY` or `CLAUDE_API_KEY`. Optional data-source settings
are listed above.

## Useful API endpoints

| Purpose | Endpoint |
| --- | --- |
| Portfolio summary and holdings | `GET /api/portfolio/summary`, `GET /api/portfolio/holdings` |
| Data-source freshness | `GET /api/portfolio/data-status` |
| Sample portfolio | `POST /api/portfolio/sync/virtual` |
| Manual transactions and snapshots | `POST /api/portfolio/transactions`, `POST /api/portfolio/snapshot` |
| eToro prices | `POST /api/prices/sync/etoro` |
| SEC company facts | `POST /api/fundamentals/sync/sec` |
| News for portfolio holdings | `POST /api/news/fetch-portfolio` |
| FRED economic data | `POST /api/macro/jobs/daily`, `POST /api/macro/jobs/monthly` |
| EUR reference rates | `POST /api/exchange-rates/sync` |
| AI chat | `POST /api/chat/message` |

The data-source sync endpoints require the credentials listed above where
applicable. The application also schedules selected refresh jobs at startup;
FRED and eToro jobs are enabled only when their credentials are configured.

For detailed configuration, endpoint examples, and database setup, see
[SETUP.md](SETUP.md).
