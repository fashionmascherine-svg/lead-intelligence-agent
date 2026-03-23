#!/usr/bin/env python3
"""
Lead Intelligence Agent
-----------------------
Entry point. Reads companies from a Google Sheet,
runs the research + qualification crew for each one,
and writes results back to the same sheet.

Usage:
    python main.py
    python main.py --max-rows 5        # Test with first 5 rows
    python main.py --dry-run           # Run agents but skip writing to sheet
"""

import argparse
import json
import time
from typing import Optional

from tqdm import tqdm

from config import config
from agents import build_crew
from tools import (
    read_companies_from_sheet,
    write_qualification_to_sheet,
    LeadQualification,
)


def parse_qualification_output(raw_output: str) -> Optional[LeadQualification]:
    """
    Parse the qualifier agent's raw output into a LeadQualification object.
    The qualifier is instructed to return a JSON object.
    We handle cases where the LLM wraps it in markdown code blocks.
    """
    # Strip markdown code blocks if present
    text = raw_output.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])  # Remove first and last line (``` markers)

    try:
        data = json.loads(text)
        return LeadQualification(
            fit_score=int(data.get("fit_score", 0)),
            fit_reason=str(data.get("fit_reason", "")),
            red_flags=str(data.get("red_flags", "")),
            suggested_angle=str(data.get("suggested_angle", "")),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"  [!] Could not parse qualification output: {e}")
        print(f"  Raw output was: {raw_output[:200]}")
        return None


def process_company(
    company: dict,
    dry_run: bool = False,
) -> bool:
    """
    Run the full research + qualification pipeline for a single company.
    Returns True on success, False on failure.
    """
    name = company["company_name"]
    website = company.get("website", "")
    notes = company.get("notes", "")
    row_index = company["row_index"]

    print(f"\n  Researching: {name} ({website or 'no website'})")

    try:
        crew = build_crew(name, website, notes)
        result = crew.kickoff()

        # CrewAI returns the output of the last task as result
        raw_output = str(result)

        qualification = parse_qualification_output(raw_output)

        if qualification is None:
            print(f"  [!] Skipping {name} — could not parse qualification")
            return False

        print(
            f"  Score: {qualification.fit_score}/100 — {qualification.fit_reason[:80]}..."
            if len(qualification.fit_reason) > 80
            else f"  Score: {qualification.fit_score}/100 — {qualification.fit_reason}"
        )

        if not dry_run:
            data_source = f"website:{website}" if website else "web_search"
            write_qualification_to_sheet(
                row_index=row_index,
                qualification=qualification,
                data_source=data_source,
            )
            print(f"  Written to sheet (row {row_index})")
        else:
            print(f"  [DRY RUN] Would write to sheet row {row_index}")

        return True

    except Exception as e:
        print(f"  [ERROR] Failed to process {name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Lead Intelligence Agent")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Max companies to process (0 = all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run agents but don't write results to Google Sheets",
    )
    args = parser.parse_args()

    # Override config max rows if passed via CLI
    if args.max_rows > 0:
        config.MAX_ROWS = args.max_rows

    print("\n=== Lead Intelligence Agent ===")
    print(f"  Sheet ID  : {config.SHEET_ID}")
    print(f"  Tab       : {config.SHEET_TAB_NAME}")
    print(f"  Model     : {config.OPENAI_MODEL}")
    print(f"  Max rows  : {config.MAX_ROWS or 'all'}")
    print(f"  Dry run   : {args.dry_run}")

    # Validate config before doing any work
    print("\nValidating configuration...")
    try:
        config.validate()
        print("  Config OK")
    except ValueError as e:
        print(str(e))
        return

    # Read companies from sheet
    print("\nReading companies from Google Sheet...")
    companies = read_companies_from_sheet()
    print(f"  Found {len(companies)} companies to process")

    if not companies:
        print("  Nothing to do. Exiting.")
        return

    # Process each company
    success_count = 0
    fail_count = 0

    for company in tqdm(companies, desc="Processing", unit="company"):
        success = process_company(company, dry_run=args.dry_run)

        if success:
            success_count += 1
        else:
            fail_count += 1

        # Rate limiting: wait between companies to avoid Apify + OpenAI rate limits
        if company != companies[-1]:
            time.sleep(config.ROW_DELAY_SECONDS)

    # Summary
    print(f"\n=== Done ===")
    print(f"  Processed : {len(companies)}")
    print(f"  Success   : {success_count}")
    print(f"  Failed    : {fail_count}")
    if not args.dry_run and success_count > 0:
        print(f"  Results written to sheet: {config.SHEET_ID}")


if __name__ == "__main__":
    main()
