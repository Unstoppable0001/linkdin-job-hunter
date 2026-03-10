"""
config.py — Load all credentials and settings from .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


def load_config() -> dict:
    return {
        # ── LinkedIn ──────────────────────────────────────────
        "linkedin_email":    os.getenv("LINKEDIN_EMAIL", ""),
        "linkedin_password": os.getenv("LINKEDIN_PASSWORD", ""),
        "search_keywords":   os.getenv(
            "SEARCH_KEYWORDS",
            "DevOps,SRE,Platform Engineer,Cloud Engineer,Infrastructure Engineer",
        ).split(","),
        "location":          os.getenv("LOCATION", "Remote"),
        "max_pages":         int(os.getenv("MAX_PAGES", "5")),

        # ── Filters ───────────────────────────────────────────
        "role_keywords": [
            "devops", "sre", "site reliability", "platform engineer",
            "cloud engineer", "infrastructure", "kubernetes", "k8s",
            "ci/cd", "devsecops", "mlops",
        ],
        "exclude_keywords":     os.getenv(
            "EXCLUDE_KEYWORDS",
            "senior,lead,principal,staff,manager,director,vp,head of",
        ).split(","),
        "max_experience_years": int(os.getenv("MAX_EXPERIENCE_YEARS", "2")),
        "experience_phrases": [
            "0-2 years", "0–2 years", "1-2 years", "entry level",
            "junior", "fresher", "graduate", "recent grad", "0+ years",
            "up to 2 years", "less than 2 years",
        ],

        # ── Freshness ─────────────────────────────────────────
        "freshness_minutes": int(os.getenv("FRESHNESS_MINUTES", "30")),

        # ── Telegram ──────────────────────────────────────────
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id":   os.getenv("TELEGRAM_CHAT_ID", ""),

        # # ── Google Sheets ─────────────────────────────────────
        # "gsheets_credentials_file": os.getenv("GSHEETS_CREDENTIALS_FILE", "credentials.json"),
        # "gsheets_spreadsheet_id":   os.getenv("GSHEETS_SPREADSHEET_ID", ""),
        # "gsheets_sheet_name":       os.getenv("GSHEETS_SHEET_NAME", "Jobs"),

        # ── AWS S3 ────────────────────────────────────────────
        # Leave AWS_ACCESS_KEY_ID / SECRET blank when using an IAM role
        # (GitHub Actions OIDC or EC2 instance profile).
        "s3_bucket":            os.getenv("S3_BUCKET", ""),
        "s3_prefix":            os.getenv("S3_PREFIX", "jobs"),
        "aws_region":           os.getenv("AWS_REGION", "us-east-1"),
        "aws_access_key_id":    os.getenv("AWS_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),

        # ── Misc ──────────────────────────────────────────────
        "run_once": os.getenv("RUN_ONCE", "false").lower() == "true",
        "dedup_db": os.getenv("DEDUP_DB", "seen_jobs.db"),
    }
