"""
storage.py — Saves matched jobs to Notion + Google Sheets concurrently.
"""

import asyncio
import logging
from typing import List

import httpx
import gspread
from google.oauth2.service_account import Credentials
from linkedin_scraper import Job

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1/pages"
GSHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SHEET_HEADERS = [
    "Job ID", "Title", "Company", "Location",
    "Salary", "Posted", "URL", "Scraped At"
]


class JobStorage:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    async def save_batch(self, jobs: List[Job]):
        await asyncio.gather(
            self._save_to_notion(jobs),
            self._save_to_gsheets(jobs),
        )

    # ── Notion ────────────────────────────────────────────────────────────────

    async def _save_to_notion(self, jobs: List[Job]):
        if not self.cfg.get("notion_token"):
            log.debug("  Notion: skipped (no token configured)")
            return

        headers = {
            "Authorization": f"Bearer {self.cfg['notion_token']}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            results = await asyncio.gather(
                *[self._notion_create_page(client, headers, job) for job in jobs],
                return_exceptions=True,
            )
        ok = sum(1 for r in results if not isinstance(r, Exception))
        log.info(f"  Notion: {ok}/{len(jobs)} saved")

    async def _notion_create_page(self, client, headers, job: Job):
        payload = {
            "parent": {"database_id": self.cfg["notion_database_id"]},
            "properties": {
                "Title":    {"title":    [{"text": {"content": job.title}}]},
                "Company":  {"rich_text": [{"text": {"content": job.company}}]},
                "Location": {"rich_text": [{"text": {"content": job.location}}]},
                "URL":      {"url": job.url},
                "Salary":   {"rich_text": [{"text": {"content": job.salary or ""}}]},
                "Posted":   {"rich_text": [{"text": {"content": job.posted_at}}]},
                "Status":   {"select": {"name": "New"}},
            },
        }
        resp = await client.post(NOTION_API, headers=headers, json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Notion {resp.status_code}: {resp.text[:200]}")

    # ── Google Sheets ─────────────────────────────────────────────────────────

    async def _save_to_gsheets(self, jobs: List[Job]):
        if not self.cfg.get("gsheets_spreadsheet_id"):
            log.debug("  Google Sheets: skipped (no spreadsheet ID configured)")
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._gsheets_sync_write, jobs)

    def _gsheets_sync_write(self, jobs: List[Job]):
        try:
            creds = Credentials.from_service_account_file(
                self.cfg["gsheets_credentials_file"],
                scopes=GSHEETS_SCOPES,
            )
            gc = gspread.authorize(creds)
            ws = gc.open_by_key(self.cfg["gsheets_spreadsheet_id"]).worksheet(
                self.cfg["gsheets_sheet_name"]
            )
            if not ws.row_values(1):
                ws.append_row(SHEET_HEADERS)
            ws.append_rows(
                [[j.job_id, j.title, j.company, j.location,
                  j.salary, j.posted_at, j.url, j.scraped_at] for j in jobs],
                value_input_option="RAW",
            )
            log.info(f"  Google Sheets: {len(jobs)} rows appended")
        except Exception as e:
            log.error(f"  Google Sheets error: {e}")
