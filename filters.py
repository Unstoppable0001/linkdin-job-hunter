"""
filters.py — Smart job filter
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pipeline per job:
  1. Dedup check     — skip if already seen (SQLite)
  2. Role match      — title OR description contains a role keyword
  3. Senior exclude  — title OR description contains a seniority signal
  4. Entry-level     — description matches an experience regex pattern
                       OR contains no experience mention at all (optimistic)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import re
import sqlite3
import logging
from typing import List
from linkedin_scraper import Job

log = logging.getLogger(__name__)

# ── Role keywords ─────────────────────────────────────────────────────────────
# Checked against: job title + full description (lowercased)
ROLE_KEYWORDS = [
    "devops", "sre", "site reliability", "platform engineer",
    "infrastructure engineer", "cloud engineer", "devsecops",
    "kubernetes", "k8s", "ci/cd", "gitops", "terraform",
    "aws engineer", "gcp engineer", "azure engineer",
    "systems engineer", "release engineer",
]

# ── Exclude keywords ──────────────────────────────────────────────────────────
# Checked against: job title ONLY (avoids false positives in long descriptions)
# E.g. description might say "no senior experience required" — we don't want
# that to exclude the job, so we only check the title.
EXCLUDE_KEYWORDS = [
    "senior", "sr.", "lead", "staff", "principal", "manager",
    "director", "vp ", "head of", "architect",
    # Explicit experience requirements in the title (rare but happens)
    "2+ years", "3+ years", "4+ years", "5+ years",
    "6+ years", "7+ years", "8+ years", "10+ years",
    "2 years experience", "3 years experience",
]

# ── Experience patterns ───────────────────────────────────────────────────────
# Checked against: full description (lowercased)
# Any ONE match = job is entry-level ✅
EXPERIENCE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b0[\s\-–]+1\s*(?:years?|yrs?)\b",          # "0-1 years"
        r"\bentry[\s\-]+level\b",                       # "entry-level" / "entry level"
        r"\bjunior\b",                                  # "junior"
        r"\bfresh(?:er|graduate)?\b",                   # "fresher" / "fresh graduate"
        r"\b(?:no|zero)\s+experience\b",               # "no experience required"
        r"\b0\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:exp|experience)\b",  # "0 years experience"
        r"\b1\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:exp|experience)\b",  # "1 year of experience"
        r"\bnewgrad\b",                                 # "newgrad"
        r"\bnew\s+grad\b",                              # "new grad"
        r"\bless\s+than\s+1\s*(?:year|yr)\b",         # "less than 1 year"
        r"\bup\s+to\s+1\s*(?:year|yr)\b",             # "up to 1 year"
    ]
]

# Detects ANY numeric experience requirement so we can apply the optimistic rule
_HAS_EXP_REQ = re.compile(r"\d+\+?\s*(?:years?|yrs?)", re.IGNORECASE)


class JobFilter:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._init_dedup_db()

    # ── Public ────────────────────────────────────────────────────────────────

    def apply(self, jobs: List[Job]) -> List[Job]:
        results = []
        stats = {"dup": 0, "role": 0, "senior": 0, "exp": 0, "pass": 0}

        for job in jobs:
            if self._is_duplicate(job):
                stats["dup"] += 1
                continue
            if not self._matches_role(job):
                stats["role"] += 1
                continue
            if self._is_senior(job):
                stats["senior"] += 1
                continue
            if not self._is_entry_level(job):
                stats["exp"] += 1
                continue

            self._mark_seen(job)
            results.append(job)
            stats["pass"] += 1

        log.info(
            f"  Filter stats → "
            f"dup={stats['dup']} role_miss={stats['role']} "
            f"senior={stats['senior']} overexp={stats['exp']} "
            f"✅ pass={stats['pass']}"
        )
        return results

    # ── Check: role match ─────────────────────────────────────────────────────

    def _matches_role(self, job: Job) -> bool:
        """Title OR description must contain at least one role keyword."""
        haystack = f"{job.title} {job.description}".lower()
        return any(kw in haystack for kw in ROLE_KEYWORDS)

    # ── Check: seniority exclusion ────────────────────────────────────────────

    def _is_senior(self, job: Job) -> bool:
        """
        Check TITLE ONLY for seniority signals.
        Checking the description risks false positives like:
        "no senior experience required" or "reporting to a senior engineer".
        """
        title_lower = job.title.lower()
        for kw in EXCLUDE_KEYWORDS:
            # Use word-boundary check for short tokens like "vp " to avoid
            # matching "mvp" etc.
            if kw in title_lower:
                log.debug(f"  Excluded (senior): '{job.title}' — matched '{kw}'")
                return True
        return False

    # ── Check: entry-level experience ─────────────────────────────────────────

    def _is_entry_level(self, job: Job) -> bool:
        """
        Returns True if the job description signals 0–1 yr experience OR
        makes no numeric experience requirement at all (optimistic include).

        Logic:
          1. If any EXPERIENCE_PATTERN matches → ✅ entry-level
          2. Else if description has NO numeric "X years" mention → ✅ optimistic include
          3. Otherwise → ❌ over-experienced, skip
        """
        text = f"{job.title} {job.description}".lower()

        # Step 1: explicit entry-level pattern
        for pattern in EXPERIENCE_PATTERNS:
            if pattern.search(text):
                log.debug(f"  Entry-level match: '{pattern.pattern}' in '{job.title}'")
                return True

        # Step 2: no experience requirement stated at all → optimistically include
        if not _HAS_EXP_REQ.search(text):
            log.debug(f"  Entry-level (optimistic, no exp req found): '{job.title}'")
            return True

        # Step 3: has numeric experience req but didn't match entry-level patterns
        log.debug(f"  Over-experienced: '{job.title}'")
        return False

    # ── Deduplication (SQLite) ────────────────────────────────────────────────

    def _init_dedup_db(self):
        self.conn = sqlite3.connect(self.cfg.get("dedup_db", "seen_jobs.db"))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS seen (
                job_id   TEXT PRIMARY KEY,
                seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _is_duplicate(self, job: Job) -> bool:
        cur = self.conn.execute("SELECT 1 FROM seen WHERE job_id = ?", (job.job_id,))
        return cur.fetchone() is not None

    def _mark_seen(self, job: Job):
        self.conn.execute(
            "INSERT OR IGNORE INTO seen (job_id) VALUES (?)", (job.job_id,)
        )
        self.conn.commit()
