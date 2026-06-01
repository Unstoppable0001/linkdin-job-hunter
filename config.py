"""
config.py — Load all credentials and settings from .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


def load_config() -> dict:
    return {
        # ── LinkedIn Jobs ──────────────────────────────────────────
        "linkedin_email":      os.getenv("LINKEDIN_EMAIL", ""),
        "linkedin_password":   os.getenv("LINKEDIN_PASSWORD", ""),
        "linkedin_li_at":      os.getenv("LINKEDIN_LI_AT", ""),
        "linkedin_jsessionid": os.getenv("LINKEDIN_JSESSIONID", ""),
        "search_keywords":   os.getenv(
            "SEARCH_KEYWORDS",
            "DevOps,SRE,Platform Engineer,Cloud Engineer,Infrastructure Engineer",
        ).split(","),
        "location":          os.getenv("LOCATION", "Remote"),
        "max_pages":         int(os.getenv("MAX_PAGES", "5")),

        # ── LinkedIn People Search ──────────────────────────────────
        "people_enabled":        os.getenv("PEOPLE_ENABLED", "false").lower() == "true",
        "people_keywords":     os.getenv(
            "PEOPLE_KEYWORDS",
            "DevOps Engineer,SRE,Platform Engineer,Cloud Engineer,Site Reliability Engineer",
        ).split(","),
        "people_countries":    os.getenv(
            "PEOPLE_COUNTRIES",
            "India,United States,United Kingdom,Germany,Canada,Australia,Singapore,Netherlands",
        ).split(","),
        "people_max_results":  int(os.getenv("PEOPLE_MAX_RESULTS", "50")),
        "people_seniority":    os.getenv(
            "PEOPLE_SENIORITY",
            "internship,entry,associate",
        ).split(","),
        "people_last_active":  int(os.getenv("PEOPLE_LAST_ACTIVE", "14")),
        "people_exclude_companies": os.getenv(
            "PEOPLE_EXCLUDE_COMPANIES",
            "recruiter,staffing,consulting,hiring,agency",
        ).split(","),
        "people_resume_required": os.getenv(
            "PEOPLE_RESUME_REQUIRED", "false"
        ).lower() == "true",
        "people_max_pages":   int(os.getenv("PEOPLE_MAX_PAGES", "3")),

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

        # ── AWS S3 ────────────────────────────────────────────
        "s3_bucket":             os.getenv("S3_BUCKET", ""),
        "s3_prefix":             os.getenv("S3_PREFIX", "jobs"),
        "aws_region":            os.getenv("AWS_REGION", "us-east-1"),
        "aws_access_key_id":     os.getenv("AWS_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),

        # ── Misc ──────────────────────────────────────────────
        "run_once": os.getenv("RUN_ONCE", "false").lower() == "true",
        "dedup_db": os.getenv("DEDUP_DB", "seen_jobs.db"),
        "people_dedup_db": os.getenv("PEOPLE_DEDUP_DB", "seen_people.db"),
    }
# 11111111111111111111111111111111111111111111"""
# config.py — Load all credentials and settings from .env
# """

# import os
# from dotenv import load_dotenv

# load_dotenv()


# def load_config() -> dict:
#     return {
#         # ── LinkedIn ──────────────────────────────────────────
#         "linkedin_email":      os.getenv("LINKEDIN_EMAIL", ""),
#         "linkedin_password":   os.getenv("LINKEDIN_PASSWORD", ""),
#         # Cookie-based auth (preferred over email/password for cloud runners)
#         "linkedin_li_at":      os.getenv("LINKEDIN_LI_AT", ""),
#         "linkedin_jsessionid": os.getenv("LINKEDIN_JSESSIONID", ""),
#         "search_keywords":   os.getenv(
#             "SEARCH_KEYWORDS",
#             "DevOps,SRE,Platform Engineer,Cloud Engineer,Infrastructure Engineer",
#         ).split(","),
#         "location":          os.getenv("LOCATION", "Remote"),
#         "max_pages":         int(os.getenv("MAX_PAGES", "5")),

#         # ── Filters ───────────────────────────────────────────
#         "role_keywords": [
#             "devops", "sre", "site reliability", "platform engineer",
#             "cloud engineer", "infrastructure", "kubernetes", "k8s",
#             "ci/cd", "devsecops", "mlops",
#         ],
#         "exclude_keywords":     os.getenv(
#             "EXCLUDE_KEYWORDS",
#             "senior,lead,principal,staff,manager,director,vp,head of",
#         ).split(","),
#         "max_experience_years": int(os.getenv("MAX_EXPERIENCE_YEARS", "2")),
#         "experience_phrases": [
#             "0-2 years", "0–2 years", "1-2 years", "entry level",
#             "junior", "fresher", "graduate", "recent grad", "0+ years",
#             "up to 2 years", "less than 2 years",
#         ],

#         # ── Freshness ─────────────────────────────────────────
#         "freshness_minutes": int(os.getenv("FRESHNESS_MINUTES", "30")),

#         # ── Telegram ──────────────────────────────────────────
#         "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
#         "telegram_chat_id":   os.getenv("TELEGRAM_CHAT_ID", ""),

#         # ── AWS S3 ────────────────────────────────────────────
#         # Tip: leave AWS_ACCESS_KEY_ID / SECRET blank when using
#         # GitHub Actions OIDC or an EC2/ECS IAM role — boto3 picks
#         # up credentials automatically from the environment.
#         "s3_bucket":             os.getenv("S3_BUCKET", ""),
#         "s3_prefix":             os.getenv("S3_PREFIX", "jobs"),
#         "aws_region":            os.getenv("AWS_REGION", "us-east-1"),
#         "aws_access_key_id":     os.getenv("AWS_ACCESS_KEY_ID", ""),
#         "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),

#         # ── Misc ──────────────────────────────────────────────
#         "run_once": os.getenv("RUN_ONCE", "false").lower() == "true",
#         "dedup_db": os.getenv("DEDUP_DB", "seen_jobs.db"),
#     }
