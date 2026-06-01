"""
people_scraper.py — Search LinkedIn People Search.

Uses authenticated session (li_at cookie required) to hit
the /voyager/api/search/cluster endpoint with PEOPLE filter.

Falls back to the public /search/people/ HTML page if API fails.
"""

import asyncio
import json
import logging
import re
from typing import List, Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from person import Person

log = logging.getLogger(__name__)

# ── Country → LinkedIn geoUrn ────────────────────────────────────────────
GEO_URN_MAP = {
    "india":          "urn:li:geo:102713980",
    "united states":  "urn:li:geo:103644278",
    "uk":             "urn:li:geo:102614886",
    "united kingdom": "urn:li:geo:102614886",
    "germany":        "urn:li:geo:103350849",
    "canada":         "urn:li:geo:103124627",
    "australia":      "urn:li:geo:101105033",
    "singapore":      "urn:li:geo:104014144",
    "netherlands":    "urn:li:geo:102531337",
    "france":         "urn:li:geo:104103811",
    "spain":          "urn:li:geo:105145774",
    "brazil":         "urn:li:geo:106712446",
    "japan":          "urn:li:geo:104350164",
    "uae":            "urn:li:geo:104440727",
    "saudi arabia":   "urn:li:geo:105230723",
    "south africa":   "urn:li:geo:104342144",
    "mexico":         "urn:li:geo:103615591",
    "ireland":        "urn:li:geo:102263331",
    "sweden":         "urn:li:geo:105215376",
    "norway":         "urn:li:geo:105094116",
    "denmark":        "urn:li:geo:104223891",
    "switzerland":    "urn:li:geo:104294730",
    "italy":          "urn:li:geo:104270673",
    "poland":         "urn:li:geo:103975053",
    "china":          "urn:li:geo:104337603",
    "hong kong":      "urn:li:geo:104153697",
    "new zealand":    "urn:li:geo:105366668",
    "malaysia":       "urn:li:geo:104076269",
    "indonesia":      "urn:li:geo:104215952",
    "philippines":    "urn:li:geo:104190618",
    "thailand":       "urn:li:geo:104049755",
    "vietnam":        "urn:li:geo:104336949",
    "pakistan":       "urn:li:geo:104198849",
    "bangladesh":     "urn:li:geo:104195143",
    "sri lanka":      "urn:li:geo:104250802",
    "nepal":          "urn:li:geo:104176533",
    "egypt":          "urn:li:geo:104169630",
    "israel":         "urn:li:geo:104389403",
    "kenya":          "urn:li:geo:104106765",
    "nigeria":        "urn:li:geo:104262228",
    "ghana":          "urn:li:geo:104198660",
    "remote":         None,
    "worldwide":      None,
    "global":         None,
}

# Country name → ISO-2 code
COUNTRY_CODE_MAP = {
    "india": "in", "united states": "us", "united kingdom": "gb",
    "germany": "de", "canada": "ca", "australia": "au",
    "singapore": "sg", "netherlands": "nl", "france": "fr",
    "spain": "es", "brazil": "br", "japan": "jp",
    "uae": "ae", "saudi arabia": "sa", "south africa": "za",
    "mexico": "mx", "ireland": "ie", "sweden": "se",
    "norway": "no", "denmark": "dk", "switzerland": "ch",
    "italy": "it", "poland": "pl", "china": "cn",
    "hong kong": "hk", "new zealand": "nz", "malaysia": "my",
    "indonesia": "id", "philippines": "ph", "thailand": "th",
    "vietnam": "vn", "pakistan": "pk", "bangladesh": "bd",
    "sri lanka": "lk", "nepal": "np", "egypt": "eg",
    "israel": "il", "kenya": "ke", "nigeria": "ng",
    "ghana": "gh", "remote": "remote", "worldwide": "global",
    "global": "global",
}

# Seniority level → LinkedIn facet value
SENIORITY_FACET = {
    "internship": "S",
    "entry":      "E",
    "associate":  "A",
    "mid":        "M",
    "senior":     "O",
    "director":   "D",
    "vp":         "V",
    "owner":      "X",
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
    "x-li-track": json.dumps({"clientVersion": "1.13.8465"}),
    "Referer": "https://www.linkedin.com/search/results/people/",
    "Origin": "https://www.linkedin.com",
}


class LinkedInPeopleScraper:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.people: List[Person] = []
        self._seen_keys: set = set()

    # ── Public ──────────────────────────────────────────────────────────────

    async def fetch_people(self) -> List[Person]:
        li_at = self.cfg.get("linkedin_li_at", "")
        jsessionid = self.cfg.get("linkedin_jsessionid", "")

        if not li_at and not jsessionid:
            log.warning(
                "  ⚠️  No li_at/jsessionid cookie. People search needs auth. "
                "Set LINKEDIN_LI_AT in .env"
            )
            return []

        cookies = {}
        if li_at:      cookies["li_at"]      = li_at
        if jsessionid: cookies["jsessionid"] = jsessionid

        async with httpx.AsyncClient(
            headers=HEADERS,
            cookies=cookies,
            timeout=30,
            follow_redirects=True,
        ) as client:
            for kw in self.cfg.get("people_keywords", []):
                for country in self.cfg.get("people_countries", []):
                    await self._search_one(
                        client, kw.strip(), country.strip()
                    )
                    await asyncio.sleep(5)

        log.info(f"  People Scraper: collected {len(self.people)} profiles")
        return self.people

    # ── Search ──────────────────────────────────────────────────────────────

    async def _search_one(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        country: str,
    ):
        max_pages = self.cfg.get("people_max_pages", 3)
        per_page = 10
        geo_urn = self._get_geo_urn(country)
        country_code = self._get_country_code(country)

        log.info(f"  🔍 Searching people: '{keyword}' in {country}")

        for page in range(max_pages):
            start = page * per_page
            try:
                results = await self._search_api(
                    client, keyword, geo_urn, start
                )
            except Exception as e:
                log.debug(f"    API search failed: {e}, trying HTML fallback")
                results = await self._search_html(
                    client, keyword, country, start
                )

            if not results:
                log.info(f"    No more results at page {page + 1}")
                break

            for r in results:
                # Dedup by profile_id
                if r.profile_id in self._seen_keys:
                    continue
                self._seen_keys.add(r.profile_id)

                # Filter by seniority (per-user setting)
                if not self._matches_seniority(r):
                    continue

                # Filter by company blacklist
                if self._excluded_company(r):
                    continue

                r.source_keyword = keyword
                r.source_country = country
                self.people.append(r)

            await asyncio.sleep(3)

    async def _search_api(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        geo_urn: Optional[str],
        start: int,
    ) -> List[Person]:
        """
        Call the voyager People
