import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent / ".env")


class Config:
    """
    Central config loader. Reads from environment variables.
    Raises clear errors if required keys are missing.
    """

    # --- LLM ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # --- Apify ---
    APIFY_API_TOKEN: str = os.getenv("APIPY_API_TOKEN", "")

    # --- Google Sheets ---
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service_account.json"
    )
    SHEET_ID: str = os.getenv("SHEET_ID", "")
    SHEET_TAB_NAME: str = os.getenv("SHEET_TAB_NAME", "Sheet1")

    # --- Sheet column names ---
    COMPANY_NAME_COLUMN: str = os.getenv("COMPANY_NAME_COLUMN", "company_name")
    WEBSITE_COLUMN: str = os.getenv("WEBSITE_COLUMN", "website")

    # --- Run settings ---
    MAX_ROWS: int = int(os.getenv("MAX_ROWS", "0"))  # 0 = process all
    ROW_DELAY_SECONDS: int = int(os.getenv("ROW_DELAY_SECONDS", "2"))

    # Output columns that the agent will write to the sheet
    OUTPUT_COLUMNS = [
        "fit_score",
        "fit_reason",
        "red_flags",
        "suggested_angle",
        "data_source",
        "enriched_at",
    ]

    @classmethod
    def validate(cls) -> None:
        """
        Call this at startup to catch missing config early.
        Raises ValueError with a clear message for each missing key.
        """
        errors = []

        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is not set")

        if not cls.APIFY_API_TOKEN:
            errors.append("APIPY_API_TOKEN is not set")

        if not cls.SHEET_ID:
            errors.append("SHEET_ID is not set")

        credentials_path = Path(cls.GOOGLE_SERVICE_ACCOUNT_JSON)
        if not credentials_path.exists():
            errors.append(
                f"Google service account file not found: {cls.GOOGLE_SERVICE_ACCOUNT_JSON}\n"
                "  -> Create a service account in Google Cloud Console and download the JSON key."
            )

        if errors:
            raise ValueError(
                "\n\nConfiguration errors found:\n"
                + "\n".join(f"  - {e}" for e in errors)
                + "\n\nSee .env.example for setup instructions."
            )


config = Config()
