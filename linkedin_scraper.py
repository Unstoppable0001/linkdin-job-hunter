"""
linkedin_scraper.py — Scrapes LinkedIn Jobs using the public guest API + httpx.
No login required. No Playwright redirects. Fast and reliable.

LinkedIn guest API:
  https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
  Returns paginated HTML job cards — no auth needed.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
JOB_DETAIL_URL   = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class Job:
    job_id:      str
    title:       str
    company:     str
    location:    str
    description: str
    url:         str
    posted_at:   str
    experience:  str = ""
    salary:      str = ""
    tags:        List[str] = field(default_factory=list)
    scraped_at:  str = field(default_factory=lambda: datetime.utcnow().isoformat())


class LinkedInScraper:
    def __init__(self, cfg: dict):
        self.cfg  = cfg
        self.jobs: List[Job] = []

    async def fetch_jobs(self) -> List[Job]:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            for keyword in self.cfg["search_keywords"]:
                await self._search_keyword(client, keyword.strip())
                await asyncio.sleep(2)

        log.info(f"  Scraper: collected {len(self.jobs)} jobs total")
        return self.jobs

    async def _search_keyword(self, client: httpx.AsyncClient, keyword: str):
        location        = self.cfg.get("location", "India")
        max_pages       = self.cfg.get("max_pages", 5)
        freshness_secs  = self.cfg.get("freshness_minutes", 180) * 60

        for page_num in range(max_pages):
            params = {
                "keywords": keyword,
                "location": location,
                "f_TPR":    f"r{freshness_secs}",   # posted within freshness window
                "f_E":      "1,2",                   # Entry level + Internship
                "sortBy":   "DD",                    # Most recent
                "start":    page_num * 25,
            }

            try:
                resp = await client.get(GUEST_SEARCH_URL, params=params)
                resp.raise_for_status()
            except Exception as e:
                log.warning(f"  Search failed for '{keyword}' page {page_num + 1}: {e}")
                break

            soup  = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")
            log.info(f"  '{keyword}' page {page_num + 1}: {len(cards)} cards")

            if not cards:
                break

            for card in cards:
                job = await self._parse_card(client, card, keyword)
                if job:
                    self.jobs.append(job)

            await asyncio.sleep(1.5)

    async def _parse_card(self, client: httpx.AsyncClient, card, keyword: str) -> "Job | None":
        try:
            # ── Extract job ID ────────────────────────────────────────────────
            job_id = None
            base_card = card.find("div", {"data-entity-urn": True})
            if base_card:
                urn = base_card["data-entity-urn"]
                job_id = urn.split(":")[-1]
            if not job_id:
                link = card.find("a", href=re.compile(r"/jobs/view/(\d+)"))
                if link:
                    m = re.search(r"/jobs/view/(\d+)", link["href"])
                    job_id = m.group(1) if m else None
            if not job_id:
                return None

            # ── Basic info from card ──────────────────────────────────────────
            title_el   = card.find("h3", class_=re.compile("base-search-card__title|job-card"))
            company_el = card.find("h4", class_=re.compile("base-search-card__subtitle"))
            loc_el     = card.find("span", class_=re.compile("job-search-card__location|base-search-card__metadata"))
            time_el    = card.find("time")

            title    = title_el.get_text(strip=True)   if title_el   else "N/A"
            company  = company_el.get_text(strip=True) if company_el else "N/A"
            location = loc_el.get_text(strip=True)     if loc_el     else "N/A"
            posted   = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else "N/A"

            if title == "N/A" and company == "N/A":
                return None

            # ── Fetch full job description ────────────────────────────────────
            desc = ""
            try:
                detail_resp = await client.get(JOB_DETAIL_URL.format(job_id=job_id))
                detail_resp.raise_for_status()
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

                desc_el = (
                    detail_soup.find("div", class_=re.compile("description__text")) or
                    detail_soup.find("section", class_=re.compile("description")) or
                    detail_soup.find("div", {"id": "job-details"})
                )
                desc = desc_el.get_text(separator=" ", strip=True) if desc_el else ""

                salary_el = detail_soup.find("div", class_=re.compile("salary|compensation"))
                salary    = salary_el.get_text(strip=True) if salary_el else ""
            except Exception as e:
                log.debug(f"  Detail fetch failed for {job_id}: {e}")
                salary = ""

            await asyncio.sleep(0.5)

            return Job(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                description=desc,
                url=f"https://www.linkedin.com/jobs/view/{job_id}/",
                posted_at=posted,
                salary=salary,
            )

        except Exception as e:
            log.debug(f"  Card parse error: {e}")
            return None
