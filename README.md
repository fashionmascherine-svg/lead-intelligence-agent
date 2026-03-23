# Lead Intelligence Agent

An AI agent that takes a list of companies, enriches each one with public web data, and qualifies them as leads using an LLM — all written to a Google Sheet automatically.

No manual research. No copy-pasting. Just structured, scored output ready for outreach.

---

## How it works

```
Input: Google Sheet with company names
    ↓
[Researcher Agent]
  - Scrapes company website
  - Pulls public LinkedIn data via Apify
  - Extracts: size, industry, tech stack signals, recent news
    ↓
[Qualifier Agent]
  - LLM scores each company (0-100)
  - Adds: fit_reason, red_flags, suggested_angle
    ↓
Output: same Google Sheet, new columns added
```

---

## Quickstart

**1. Clone and install**

```bash
git clone https://github.com/fashionmascherine-svg/lead-intelligence-agent.git
cd lead-intelligence-agent
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Fill in your keys (see Configuration section below)
```

**3. Prepare your Google Sheet**

Your input sheet must have at least these columns:

| company_name | website | notes |
|---|---|---|
| Acme Corp | acme.com | SaaS, Series B |

**4. Run the agent**

```bash
python main.py --sheet-id YOUR_GOOGLE_SHEET_ID
```

The agent will add new columns to your sheet:
`fit_score`, `fit_reason`, `red_flags`, `suggested_angle`, `data_source`, `enriched_at`

---

## Configuration

Copy `.env.example` to `.env` and fill in:

```env
# OpenAI (used by qualifier agent)
OPENAI_API_KEY=sk-...

# Apify (used by researcher agent for web scraping)
APIPY_API_TOKEN=apify_api_...

# Google Sheets (service account JSON path)
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service_account.json

# Target sheet
SHEET_ID=your_google_sheet_id_here
SHEET_TAB_NAME=Sheet1
```

**Google Sheets auth setup (one-time):**
1. Create a service account in Google Cloud Console
2. Enable the Google Sheets API
3. Download the JSON key and save it to `credentials/service_account.json`
4. Share your Google Sheet with the service account email

---

## Project structure

```
lead-intelligence-agent/
├── main.py              # Entry point — runs the full pipeline
├── agents.py            # CrewAI agent definitions
├── tools.py             # Apify scraper + Google Sheets writer tools
├── config.py            # Loads env vars and validates config
├── requirements.txt
├── .env.example
├── credentials/         # Put your service_account.json here (gitignored)
└── README.md
```

---

## Output example

| company_name | fit_score | fit_reason | red_flags | suggested_angle |
|---|---|---|---|---|
| Acme Corp | 82 | Series B SaaS, growing sales team, no automation tooling visible | Competitor already using similar tool | Lead with ROI angle, reference similar company |
| Beta Ltd | 34 | Small team, no budget signals | Early stage, founder-led sales | Not a fit now, revisit in 6 months |

---

## Stack

- **[CrewAI](https://github.com/joaomdmoura/crewAI)** — multi-agent orchestration
- **[Apify](https://apify.com)** — web scraping (website + LinkedIn data)
- **[gspread](https://github.com/burnash/gspread)** — Google Sheets read/write
- **OpenAI GPT-4o** — lead qualification and scoring
- **Python 3.11+**

---

## What I learned building this

- CrewAI's task context passing is powerful but requires explicit output formatting — if you let agents write free text, the next agent in the chain gets confused. Use Pydantic models for structured handoffs.
- Apify actors return different schemas depending on the target site. Build a normalization layer early, not after.
- Google Sheets API rate limits are 100 requests/100 seconds — batch your writes, never write row by row in a loop.
- LLM scoring is only as good as the context you give it. A company name alone gives a garbage score. Website content + tech signals + team size = actually useful output.

---

## Roadmap

- [ ] Add Telegram group monitoring as enrichment signal
- [ ] Webhook output to HubSpot / Pipedrive
- [ ] Deduplication logic for recurring runs
- [ ] Confidence score on scraped data quality

---

## License

MIT
