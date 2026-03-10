"""
linkedin_scraper.py — Scrapes LinkedIn Jobs using Playwright (headless browser)
Bypasses basic bot detection with realistic delays and user-agent rotation.
"""

import asyncio
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from playwright.async_api import async_playwright, Page

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
]


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
        self.cfg = cfg
        self.jobs: List[Job] = []

    async def fetch_jobs(self) -> List[Job]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            await self._login(page)

            for keyword in self.cfg["search_keywords"]:
                await self._search_keyword(page, keyword.strip())
                await asyncio.sleep(random.uniform(2, 4))  # polite delay

            await browser.close()

        log.info(f"  Scraper: collected {len(self.jobs)} jobs total")
        return self.jobs

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _login(self, page: Page):
        """Log into LinkedIn once per session."""
        await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
        await page.fill("#username", self.cfg["linkedin_email"])
        await page.fill("#password", self.cfg["linkedin_password"])
        await page.click('[type="submit"]')
        await page.wait_for_url("**/feed/**", timeout=15000)
        log.info("  LinkedIn login successful")
        await asyncio.sleep(random.uniform(1, 2))

    async def _search_keyword(self, page: Page, keyword: str):
        location = self.cfg["location"]
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={keyword.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}"
            f"&f_E=1,2"          # Experience: Internship + Entry level
            f"&sortBy=DD"        # Most recent first
        )

        for page_num in range(self.cfg["max_pages"]):
            paginated = url + f"&start={page_num * 25}"
            await page.goto(paginated, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 3))

            # Scroll to load all cards
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            job_cards = await page.query_selector_all(".job-card-container")
            if not job_cards:
                break

            for card in job_cards:
                job = await self._parse_card(page, card)
                if job:
                    self.jobs.append(job)

    async def _parse_card(self, page: Page, card) -> Job | None:
        try:
            await card.click()
            await asyncio.sleep(random.uniform(0.8, 1.5))

            detail = page.locator(".jobs-details")

            title    = await self._safe_text(detail, ".job-details-jobs-unified-top-card__job-title")
            company  = await self._safe_text(detail, ".job-details-jobs-unified-top-card__company-name")
            location = await self._safe_text(detail, ".job-details-jobs-unified-top-card__bullet")
            desc     = await self._safe_text(detail, ".jobs-description-content__text")
            posted   = await self._safe_text(detail, ".job-details-jobs-unified-top-card__posted-date")
            salary   = await self._safe_text(detail, ".job-details-jobs-unified-top-card__job-insight span", default="")

            job_url  = page.url
            job_id   = job_url.split("/jobs/view/")[-1].split("?")[0] if "/jobs/view/" in job_url else job_url[-12:]

            return Job(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                description=desc,
                url=job_url,
                posted_at=posted,
                salary=salary,
            )
        except Exception as e:
            log.debug(f"  Card parse error: {e}")
            return None

    @staticmethod
    async def _safe_text(parent, selector: str, default: str = "N/A") -> str:
        try:
            el = parent.locator(selector).first
            return (await el.inner_text()).strip()
        except Exception:
            return default
