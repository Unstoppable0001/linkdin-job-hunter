"""
people_scraper.py — Search LinkedIn People Search API.

Uses the LinkedIn People Search (Sales Navigator / Recruiter Lite style)
endpoint accessible via authenticated session cookies (li_at + jsessionid).

Search endpoint:
  https://www.linkedin.com/voyager/api/search/cluster
  ?pt=PEOPLE&pagingStart=0&keywords=DevOps+Engineer&geoUrn=...

Fallback: scrapes the public people search page (/search?keywords=...&type=P)

IMPORTANT: li_at cookie is REQUIRED for people search.
Set LINKEDIN_LI_AT in your .env file.
"""

import asyncio
import logging
import re
from typing import List, Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from person import Person

log = logging.getLogger(__name__)

# ── Country name → LinkedIn geoUrn mapping ────────────────────────────────────
# LinkedIn uses numeric geoURNs for countries/regions.
# Format: "urn:li:geo:{id}"
GEO_URN_MAP = {
    # Countries
    "india":                "urn:li:geo:102713980",   # India
    "united states":        "urn:li:geo:103644278",   # United States
    "united kingdom":       "urn:li:geo:102614886",   # United Kingdom
    "germany":              "urn:li:geo:103350849",   # Germany
    "canada":               "urn:li:geo:103124627",   # Canada
    "australia":           "urn:li:geo:101105033",   # Australia
    "singapore":            "urn:li:geo:104014144",   # Singapore
    "netherlands":          "urn:li:geo:102531337",   # Netherlands
    "france":               "urn:li:geo:104103811",   # France
    "spain":                "urn:li:geo:105145774",   # Spain
    "brazil":               "urn:li:geo:106712446",   # Brazil
    "japan":                "urn:li:geo:104350164",   # Japan
    "uae":                  "urn:li:geo:104440727",   # UAE
    "saudi arabia":         "urn:li:geo:105230723",   # Saudi Arabia
    "south africa":         "urn:li:geo:104342144",   # South Africa
    "mexico":               "urn:li:geo:103615591",   # Mexico
    "ireland":              "urn:li:geo:102263331",   # Ireland
    "sweden":               "urn:li:geo:105215376",   # Sweden
    "norway":               "urn:li:geo:105094116",   # Norway
    "denmark":              "urn:li:geo:104223891",   # Denmark
    "switzerland":          "urn:li:geo:104294730",   # Switzerland
    "austria":              "urn:li:geo:104538269",   # Austria
    "belgium":              "urn:li:geo:104620068",   # Belgium
    "italy":                "urn:li:geo:104270673",   # Italy
    "portugal":             "urn:li:geo:105108694",   # Portugal
    "poland":               "urn:li:geo:103975053",   # Poland
    "russia":               "urn:li:geo:104508485",   # Russia
    "china":                "urn:li:geo:104337603",   # China
    "hong kong":            "urn:li:geo:104153697",   # Hong Kong
    "new zealand":          "urn:li:geo:105366668",   # New Zealand
    "malaysia":             "urn:li:geo:104076269",   # Malaysia
    "indonesia":            "urn:li:geo:104215952",   # Indonesia
    "philippines":          "urn:li:geo:104190618",   # Philippines
    "thailand":             "urn:li:geo:104049755",   # Thailand
    "vietnam":              "urn:li:geo:104336949",   # Vietnam
    "pakistan":             "urn:li:geo:104198849",   # Pakistan
    "bangladesh":           "urn:li:geo:104195143",   # Bangladesh
    "sri lanka":            "urn:li:geo:104250802",   # Sri Lanka
    "nepal":                "urn:li:geo:104176533",   # Nepal
    "egypt":                "urn:li:geo:104169630",   # Egypt
    "israel":               "urn:li:geo:104389403",   # Israel
    "kenya":                "urn:li:geo:104106765",   # Kenya
    "nigeria":              "urn:li:geo:104262228",   # Nigeria
    "ghana":                "urn:li:geo:104198660",   # Ghana
    "kenya":                "urn:li:geo:104106765",   # Kenya
    "kenya":                "urn:li:geo:104106765",   # Kenya
    # Global / All
    "worldwide":            None,
    "global":               None,
    "remote":               None,
}

# ── Seniority level → LinkedIn facet values ───────────────────────────────────
SENIORITY_FACET_MAP = {
    "internship":  "S",
    "entry":       "E",
    "associate":   "A",
    "mid":         "M",
    "senior":      "O",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.linkedin.normalized+json+2.1",
    "Accept-Language": "en-US,en;q=0.9",
    "x-li-lang": "en_US",
    "x-li-track": "{}",
    "Referer": "https://www.linkedin.com/search/results/people/",
    "Origin": "https://www.linkedin.com",
}


class LinkedInPeopleScraper:
    """
    Searches LinkedIn for people matching keyword + country.
    Requires li_at cookie for authenticated access.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.people: List[Person] = []

    # ── Public API ──────────────────────────────────────────────────────────────

    async def fetch_people(self) -> List[Person]:
        """
        Main entry point. For each (keyword, country) pair,
        search LinkedIn and collect profile cards.
        """
        li_at = self.cfg.get("linkedin_li_at", "")
        jsessionid = self.cfg.get("linkedin_jsessionid", "")

        if not li_at and not jsessionid:
            log.warning(
                "  ⚠️  PEOPLE_ENABLED=true but no li_at/jsessionid cookie set. "
                "People search requires authentication. "
                "Set LINKEDIN_LI_AT in your .env file."
            )
            return []

        cookies = {}
        if li_at:
            cookies["li_at"] = li_at
        if jsessionid:
            cookies["jsessionid"] = jsessionid

        async with httpx.AsyncClient(
            headers=HEADERS,
            cookies=cookies,
            timeout=30,
            follow_redirects=True,
        ) as client:
            for keyword in self.cfg.get("people_keywords", []):
                for country in self.cfg.get("people_countries", []):
                    await self._search_keyword_country(
                        client, keyword.strip(), country.strip()
                    )
                    await asyncio.sleep(5)  # polite delay between searches

        log.info(
            f"  People Scraper: collected {len(self.people)} profiles total"
        )
        return self.people

    # ── Core search ────────────────────────────────────────────────────────────

    async def _search_keyword_country(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        country: str,
    ):
        """
        Search people by keyword within a specific country.
        Uses the /search endpoint with facets for filtering.
        """
        max_results = self.cfg.get("people_max_results", 50)
        geo_urn = self._get_geo_urn(country)
        seniority_levels = self.cfg.get("people_seniority", ["entry", "associate"])

        #
