import time
import requests
from datetime import datetime, timezone
from typing import Optional

import gspread
from apify_client import ApifyClient
from crewai.tools import tool
from google.oauth2.service_account import Credentials
from pydantic import BaseModel

from config import config


# ---------------------------------------------------------------------------
# Pydantic model for structured output from the Qualifier Agent
# ---------------------------------------------------------------------------

class LeadQualification(BaseModel):
    fit_score: int          # 0-100
    fit_reason: str         # Why this company is (or isn't) a good fit
    red_flags: str          # Concerns or blockers
    suggested_angle: str    # How to approach outreach


# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

def _get_sheet():
    """Authenticate and return the target worksheet."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(
        config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(config.SHEET_ID)
    return spreadsheet.worksheet(config.SHEET_TAB_NAME)


def read_companies_from_sheet() -> list[dict]:
    """
    Read all rows from the Google Sheet.
    Returns a list of dicts with at least 'company_name' and optionally 'website'.
    Skips rows where company_name is empty.
    """
    sheet = _get_sheet()
    rows = sheet.get_all_records()

    companies = []
    for i, row in enumerate(rows):
        name = str(row.get(config.COMPANY_NAME_COLUMN, "")).strip()
        if not name:
            continue
        companies.append({
            "row_index": i + 2,  # +2: 1-indexed + header row
            "company_name": name,
            "website": str(row.get(config.WEBSITE_COLUMN, "")).strip(),
            "notes": str(row.get("notes", "")).strip(),
        })

    if config.MAX_ROWS > 0:
        companies = companies[:config.MAX_ROWS]

    return companies


def write_qualification_to_sheet(
    row_index: int,
    qualification: LeadQualification,
    data_source: str,
) -> None:
    """
    Write qualification results back to the sheet row.
    Creates output columns if they don't exist yet.
    Batches all writes into a single API call per row.
    """
    sheet = _get_sheet()
    headers = sheet.row_values(1)

    # Ensure all output columns exist in the header row
    for col_name in config.OUTPUT_COLUMNS:
        if col_name not in headers:
            sheet.add_cols(1)
            next_col = len(headers) + 1
            sheet.update_cell(1, next_col, col_name)
            headers.append(col_name)

    # Build update payload
    updates = {
        "fit_score": str(qualification.fit_score),
        "fit_reason": qualification.fit_reason,
        "red_flags": qualification.red_flags,
        "suggested_angle": qualification.suggested_angle,
        "data_source": data_source,
        "enriched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    # Write all cells in one batch
    cell_updates = []
    for col_name, value in updates.items():
        col_index = headers.index(col_name) + 1
        cell_updates.append(
            gspread.Cell(row=row_index, col=col_index, value=value)
        )

    sheet.update_cells(cell_updates)


# ---------------------------------------------------------------------------
# CrewAI Tools
# ---------------------------------------------------------------------------

@tool("scrape_company_website")
def scrape_company_website(url: str) -> str:
    """
    Scrapes the content of a company website using Apify's Website Content Crawler.
    Returns a plain-text summary of the homepage content.
    Use this to extract: company description, services, team size signals, tech stack mentions.

    Args:
        url: The company website URL (e.g. 'https://acme.com')
    """
    if not url or url in ("", "N/A", "none"):
        return "No website URL provided."

    # Normalise URL
    if not url.startswith("http"):
        url = "https://" + url

    client = ApifyClient(config.APIFY_API_TOKEN)

    run_input = {
        "startUrls": [{"url": url}],
        "maxCrawlPages": 3,       # Homepage + 2 subpages max
        "maxCrawlDepth": 1,
        "outputFormats": ["text"],
    }

    try:
        run = client.actor("apify/website-content-crawler").call(
            run_input=run_input,
            timeout_secs=60,
        )
        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )

        if not items:
            return f"No content scraped from {url}."

        # Concatenate text from all crawled pages, truncated to avoid LLM token overload
        combined = "\n\n---\n\n".join(
            item.get("text", "")[:2000] for item in items if item.get("text")
        )
        return combined[:6000] or f"Content scraped from {url} was empty."

    except Exception as e:
        return f"Error scraping {url}: {str(e)}"


@tool("search_company_web")
def search_company_web(company_name: str) -> str:
    """
    Searches the web for information about a company using Apify's Google Search Scraper.
    Returns a summary of search results: titles, snippets, and URLs.
    Use this when no website is provided, or to find news/funding/recent activity.

    Args:
        company_name: The name of the company to search for
    """
    client = ApifyClient(config.APIFY_API_TOKEN)

    run_input = {
        "queries": [
            f"{company_name} company",
            f"{company_name} funding news 2024 2025",
        ],
        "resultsPerPage": 5,
        "maxPagesPerQuery": 1,
        "languageCode": "en",
    }

    try:
        run = client.actor("apify/google-search-scraper").call(
            run_input=run_input,
            timeout_secs=60,
        )
        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )

        if not items:
            return f"No search results found for '{company_name}'."

        results = []
        for item in items:
            for result in item.get("organicResults", [])[:5]:
                title = result.get("title", "")
                snippet = result.get("description", "")
                link = result.get("url", "")
                results.append(f"- {title}\n  {snippet}\n  {link}")

        return "\n\n".join(results)[:5000] or f"No useful results for '{company_name}'."

    except Exception as e:
        return f"Error searching for {company_name}: {str(e)}"
