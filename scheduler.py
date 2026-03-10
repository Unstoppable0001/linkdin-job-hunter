"""
scheduler.py — Runs the job-hunt cycle every N minutes using APScheduler.
Handles graceful shutdown on CTRL+C / SIGTERM.
"""

import asyncio
import logging
import signal
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)


def start_scheduler(async_fn, interval_minutes: int = 30):
    """
    Starts an async scheduler that calls `async_fn` immediately,
    then repeats every `interval_minutes`.
    """
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        async_fn,
        trigger="interval",
        minutes=interval_minutes,
        id="job_hunt",
        next_run_time=None,  # set below for immediate first run
    )
    scheduler.start()

    # Run immediately on start
    loop.run_until_complete(async_fn())

    # Then schedule repeating runs
    scheduler.reschedule_job("job_hunt", trigger="interval", minutes=interval_minutes)

    log.info(f"⏰  Scheduler running — next cycle in {interval_minutes} minutes")

    # Graceful shutdown
    def _shutdown(sig, frame):
        log.info("🛑 Shutdown signal received — stopping scheduler...")
        scheduler.shutdown(wait=False)
        loop.stop()

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_forever()
    finally:
        log.info("👋 Job Hunter stopped.")
