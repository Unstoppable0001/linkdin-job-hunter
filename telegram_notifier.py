"""
telegram_notifier.py — Sends instant Telegram alerts with rich formatting.
Groups jobs into a digest if > 5, sends individually if ≤ 5.
"""

import asyncio
import logging
import httpx
from typing import List
from linkedin_scraper import Job

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

ROLE_EMOJI = {
    "devops":       "⚙️",
    "sre":          "🔧",
    "platform":     "🏗️",
    "cloud":        "☁️",
    "kubernetes":   "🐳",
    "infrastructure": "🖥️",
}


def _emoji_for(title: str) -> str:
    tl = title.lower()
    for kw, em in ROLE_EMOJI.items():
        if kw in tl:
            return em
    return "💼"


def _format_job(job: Job) -> str:
    em = _emoji_for(job.title)
    salary_line = f"\n💰 *Salary:* {job.salary}" if job.salary and job.salary != "N/A" else ""
    return (
        f"{em} *{job.title}*\n"
        f"🏢 {job.company}\n"
        f"📍 {job.location}\n"
        f"🕐 Posted: {job.posted_at}"
        f"{salary_line}\n"
        f"🔗 [View Job]({job.url})"
    )


def _format_digest(jobs: List[Job]) -> str:
    lines = ["🚨 *Job Hunt Digest* — New Matches Found!\n"]
    for i, job in enumerate(jobs, 1):
        em = _emoji_for(job.title)
        lines.append(f"{i}. {em} [{job.title}]({job.url}) — _{job.company}_")
    lines.append(f"\n📊 *{len(jobs)} new roles* matched your filters.")
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, cfg: dict):
        self.token   = cfg["telegram_bot_token"]
        self.chat_id = cfg["telegram_chat_id"]
        self.base    = TELEGRAM_API.format(token=self.token, method="{method}")

    async def send_batch(self, jobs: List[Job]):
        if len(jobs) > 5:
            await self._send_message(_format_digest(jobs))
        else:
            for job in jobs:
                await self._send_message(_format_job(job))
                await asyncio.sleep(0.5)  # avoid hitting rate limits

    async def _send_message(self, text: str):
        url = self.base.format(method="sendMessage")
        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                log.warning(f"  Telegram error {resp.status_code}: {resp.text}")
            else:
                log.debug("  Telegram message sent OK")
