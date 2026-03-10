"""
time_filter.py — Parses LinkedIn's relative timestamps and filters
only jobs posted within the last N minutes (default 30).

LinkedIn posts times like:
  "Just now" / "1 minute ago" / "23 minutes ago"
  "1 hour ago" / "3 hours ago"
  "Today" / "Yesterday" / "2 days ago"

Anything beyond the freshness_minutes window is dropped.
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from linkedin_scraper import Job

log = logging.getLogger(__name__)


class TimeFilter:
    """
    Converts LinkedIn human-readable timestamps → UTC datetimes,
    then keeps only jobs posted within `freshness_minutes`.
    """

    def __init__(self, freshness_minutes: int = 30):
        self.freshness_minutes = freshness_minutes
        self.cutoff_delta = timedelta(minutes=freshness_minutes)

    # ─────────────────────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────────────────────

    def apply(self, jobs: List[Job]) -> List[Job]:
        now = datetime.now(timezone.utc)
        cutoff = now - self.cutoff_delta

        fresh, stale = [], []
        for job in jobs:
            posted_dt = self.parse_posted_at(job.posted_at, reference=now)
            if posted_dt is None:
                # Can't determine time → include optimistically
                log.info(f"  TimeFilter: unparseable '{job.posted_at}' — keeping '{job.title}'")
                fresh.append(job)
            elif posted_dt >= cutoff:
                log.info(f"  TimeFilter: FRESH ({job.posted_at}) → {job.title} @ {job.company}")
                fresh.append(job)
            else:
                delta_min = int((now - posted_dt).total_seconds() / 60)
                log.info(f"  TimeFilter: STALE by {delta_min}min ({job.posted_at}) → {job.title}")
                stale.append(job)

        log.info(
            f"  TimeFilter: {len(fresh)} fresh (≤{self.freshness_minutes}min), "
            f"{len(stale)} stale dropped"
        )
        return fresh

    # ─────────────────────────────────────────────────────────────────────────
    # Timestamp parser
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_posted_at(raw: str, reference: datetime = None) -> datetime | None:
        """
        Converts a LinkedIn relative time string into an absolute UTC datetime.
        Returns None if the string cannot be parsed.
        """
        if reference is None:
            reference = datetime.now(timezone.utc)

        raw = raw.strip().lower()

        # ── "just now" ────────────────────────────────────────────────────────
        if raw in ("just now", "now", "moments ago"):
            return reference

        # ── "X seconds ago" ───────────────────────────────────────────────────
        m = re.match(r"(\d+)\s+seconds?\s+ago", raw)
        if m:
            return reference - timedelta(seconds=int(m.group(1)))

        # ── "X minutes ago" / "Xm ago" ────────────────────────────────────────
        m = re.match(r"(\d+)\s*(?:minutes?|mins?|m)\s+ago", raw)
        if m:
            return reference - timedelta(minutes=int(m.group(1)))

        # ── "X hours ago" / "Xh ago" ──────────────────────────────────────────
        m = re.match(r"(\d+)\s*(?:hours?|hrs?|h)\s+ago", raw)
        if m:
            return reference - timedelta(hours=int(m.group(1)))

        # ── "X days ago" ──────────────────────────────────────────────────────
        m = re.match(r"(\d+)\s+days?\s+ago", raw)
        if m:
            return reference - timedelta(days=int(m.group(1)))

        # ── "X weeks ago" ─────────────────────────────────────────────────────
        m = re.match(r"(\d+)\s+weeks?\s+ago", raw)
        if m:
            return reference - timedelta(weeks=int(m.group(1)))

        # ── "X months ago" ────────────────────────────────────────────────────
        m = re.match(r"(\d+)\s+months?\s+ago", raw)
        if m:
            return reference - timedelta(days=int(m.group(1)) * 30)

        # ── "today" ───────────────────────────────────────────────────────────
        if raw == "today":
            return reference.replace(hour=0, minute=0, second=0, microsecond=0)

        # ── "yesterday" ───────────────────────────────────────────────────────
        if raw == "yesterday":
            return reference - timedelta(days=1)

        # ── Absolute ISO or date strings e.g. "2024-12-01" ───────────────────
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",   # LinkedIn guest API: "2026-03-10T12:30:00.000Z"
            "%Y-%m-%dT%H:%M:%SZ",       # without milliseconds
            "%Y-%m-%dT%H:%M:%S",        # without Z
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None  # unparseable


# ─────────────────────────────────────────────────────────────────────────────
# Quick unit tests (run: python time_filter.py)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from datetime import timezone

    now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    cases = [
        ("Just now",        0),
        ("5 minutes ago",   5),
        ("29 minutes ago",  29),
        ("30 minutes ago",  30),
        ("31 minutes ago",  31),
        ("1 hour ago",      60),
        ("3 hours ago",     180),
        ("Yesterday",       1440),
        ("2 days ago",      2880),
    ]

    tf = TimeFilter(freshness_minutes=30)

    print(f"\n{'Input':<22} {'Parsed offset (min)':<22} {'Within 30min?'}")
    print("─" * 60)
    for raw, expected_min in cases:
        parsed = TimeFilter.parse_posted_at(raw, reference=now)
        if parsed:
            delta_min = int((now - parsed).total_seconds() / 60)
            within = "✅ FRESH" if delta_min <= 30 else "❌ stale"
        else:
            delta_min = "?"
            within = "⚠️  unparseable"
        print(f"{raw:<22} {str(delta_min):<22} {within}")

# NOTE: Since LinkedIn's f_TPR parameter already pre-filters by time at the API level,
# TimeFilter acts as a secondary safety net. If you see 0 fresh jobs consistently,
# consider increasing FRESHNESS_MINUTES env var to match or exceed your cron interval.
