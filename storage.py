"""
storage.py — Saves matched jobs to AWS S3 as both CSV and JSON.

S3 layout:
  s3://<bucket>/jobs/YYYY/MM/DD/<run_id>.json   — full job objects (JSON)
  s3://<bucket>/jobs/YYYY/MM/DD/<run_id>.csv    — spreadsheet-friendly CSV
  s3://<bucket>/jobs/latest.json                — last run snapshot (overwritten)
  s3://<bucket>/jobs/latest.csv                 — last run CSV (overwritten)
"""

import asyncio
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from linkedin_scraper import Job

log = logging.getLogger(__name__)

CSV_HEADERS = [
    "job_id", "title", "company", "location",
    "salary", "posted_at", "url", "scraped_at",
]


class JobStorage:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    async def save_batch(self, jobs: List[Job]):
        """Persist jobs to S3 as CSV + JSON concurrently."""
        if not self.cfg.get("s3_bucket"):
            log.warning("  Storage: S3_BUCKET not set — skipping storage")
            return
        await asyncio.gather(
            self._upload_json(jobs),
            self._upload_csv(jobs),
        )

    # ── JSON ──────────────────────────────────────────────────────────────────

    async def _upload_json(self, jobs: List[Job]):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._s3_put_json, jobs)

    def _s3_put_json(self, jobs: List[Job]):
        now_utc = datetime.now(timezone.utc)
        run_id  = self._run_id()
        payload = self._build_payload(jobs, now_utc, run_id)
        body    = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        dated_key  = self._dated_key(now_utc, run_id, "json")
        latest_key = f"{self.cfg.get('s3_prefix', 'jobs')}/latest.json"

        self._put(dated_key,  body, "application/json")
        self._put(latest_key, body, "application/json")
        log.info(f"  S3 JSON: {len(jobs)} jobs → s3://{self.cfg['s3_bucket']}/{dated_key}")

    # ── CSV ───────────────────────────────────────────────────────────────────

    async def _upload_csv(self, jobs: List[Job]):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._s3_put_csv, jobs)

    def _s3_put_csv(self, jobs: List[Job]):
        now_utc = datetime.now(timezone.utc)
        run_id  = self._run_id()

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for j in jobs:
            writer.writerow({
                "job_id":     j.job_id,
                "title":      j.title,
                "company":    j.company,
                "location":   j.location,
                "salary":     j.salary,
                "posted_at":  j.posted_at,
                "url":        j.url,
                "scraped_at": j.scraped_at,
            })
        body = buf.getvalue().encode("utf-8")

        dated_key  = self._dated_key(now_utc, run_id, "csv")
        latest_key = f"{self.cfg.get('s3_prefix', 'jobs')}/latest.csv"

        self._put(dated_key,  body, "text/csv")
        self._put(latest_key, body, "text/csv")
        log.info(f"  S3 CSV : {len(jobs)} rows  → s3://{self.cfg['s3_bucket']}/{dated_key}")

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _put(self, key: str, body: bytes, content_type: str):
        try:
            self._s3().put_object(
                Bucket=self.cfg["s3_bucket"],
                Key=key,
                Body=body,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as e:
            log.error(f"  S3 upload failed [{key}]: {e}")
            raise

    def _s3(self):
        kwargs = {}
        if self.cfg.get("aws_access_key_id"):
            kwargs["aws_access_key_id"]     = self.cfg["aws_access_key_id"]
            kwargs["aws_secret_access_key"] = self.cfg["aws_secret_access_key"]
        if self.cfg.get("aws_region"):
            kwargs["region_name"] = self.cfg["aws_region"]
        return boto3.client("s3", **kwargs)

    def _dated_key(self, now: datetime, run_id: str, ext: str) -> str:
        prefix = self.cfg.get("s3_prefix", "jobs")
        return f"{prefix}/{now.strftime('%Y/%m/%d')}/{run_id}.{ext}"

    @staticmethod
    def _run_id() -> str:
        return str(uuid.uuid4())[:8]

    @staticmethod
    def _build_payload(jobs: List[Job], now_utc: datetime, run_id: str) -> dict:
        return {
            "run_id":     run_id,
            "scraped_at": now_utc.isoformat(),
            "count":      len(jobs),
            "jobs": [
                {
                    "job_id":      j.job_id,
                    "title":       j.title,
                    "company":     j.company,
                    "location":    j.location,
                    "salary":      j.salary,
                    "posted_at":   j.posted_at,
                    "url":         j.url,
                    "description": j.description,
                    "scraped_at":  j.scraped_at,
                    "tags":        j.tags,
                }
                for j in jobs
            ],
        }
