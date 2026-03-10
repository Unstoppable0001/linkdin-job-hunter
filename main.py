"""
main.py — AI Job Hunter System Orchestrator
Pipeline: Scrape → Role Filter → Time Filter (≤30min) → Dedup → Notify → Store
"""

import asyncio
import logging
from config import load_config
from scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("job_hunter.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


async def run_cycle():
    """One complete job-hunt cycle."""
    from linkedin_scraper import LinkedInScraper
    from filters import JobFilter
    from time_filter import TimeFilter
    from telegram_notifier import TelegramNotifier
    from storage import JobStorage

    cfg = load_config()

    log.info("=" * 55)
    log.info("🔍  Job Hunt Cycle Started")
    log.info("=" * 55)

    # Step 1: Scrape LinkedIn
    scraper = LinkedInScraper(cfg)
    raw_jobs = await scraper.fetch_jobs()
    log.info(f"  [1/4] Scraped   : {len(raw_jobs)} raw listings")

    # Step 2: Role + Experience filter
    role_filter = JobFilter(cfg)
    role_matched = role_filter.apply(raw_jobs)
    log.info(f"  [2/4] Role/Exp  : {len(role_matched)} matched (DevOps/SRE/Platform, 0-2 yrs)")

    # Step 3: Freshness filter — ONLY jobs posted in last 30 minutes
    time_filter = TimeFilter(freshness_minutes=cfg.get("freshness_minutes", 30))
    fresh_jobs = time_filter.apply(role_matched)
    log.info(f"  [3/4] Fresh     : {len(fresh_jobs)} posted within last {cfg.get('freshness_minutes', 30)} min")

    if not fresh_jobs:
        log.info("  ⏳ No fresh jobs this cycle — will retry in 30 min.")
        return

    # Step 4: Telegram + Storage
    notifier = TelegramNotifier(cfg)
    await notifier.send_batch(fresh_jobs)
    log.info(f"  [4/4] Notified  : {len(fresh_jobs)} Telegram alerts sent")

    storage = JobStorage(cfg)
    await storage.save_batch(fresh_jobs)
    log.info(f"        Stored    : {len(fresh_jobs)} jobs → Notion + Google Sheets")

    log.info(f"✅  Cycle done — {len(fresh_jobs)} new jobs delivered.\n")


if __name__ == "__main__":
    cfg = load_config()
    log.info("🚀  AI Job Hunter System — ACTIVE")
    log.info(f"    Keywords : {cfg['search_keywords']}")
    log.info(f"    Location : {cfg['location']}")
    log.info(f"    Freshness: last {cfg.get('freshness_minutes', 30)} minutes only")
    log.info(f"    Schedule : every 30 minutes\n")

    if cfg.get("run_once"):
        asyncio.run(run_cycle())
    else:
        start_scheduler(run_cycle, interval_minutes=30)
