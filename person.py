"""
person.py — Data model for LinkedIn profile candidates
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Person:
    # ── Identity ────────────────────────────────────────────────
    linkedin_url:     str
    profile_id:       str           # urn:li:fs_memberBadge:XXXX
    full_name:        str
    headline:         str           # job title / "looking for" line
    location:        str           # "Bengaluru, Karnataka, India"
    country:          str           # extracted from location
    country_code:     str           # "in", "us", "gb" etc.

    # ── Professional ───────────────────────────────────────────
    current_title:    str = ""
    current_company: str = ""
    current_company_industry: str = ""
    experience_years: int = 0
    seniority_level:  str = ""     # internship | entry | associate | mid | senior

    # ── Contact (extracted from profile/about section) ─────────
    email:            str = ""
    phone:            str = ""
    twitter:          str = ""
    website:          str = ""
    resume_url:       str = ""

    # ── Profile content ─────────────────────────────────────────
    summary:          str = ""
    skills:           List[str] = field(default_factory=list)
    certifications:   List[str] = field(default_factory=list)
    languages:        List[str] = field(default_factory=list)

    # ── LinkedIn metadata ──────────────────────────────────────
    connection_degree: str = ""    # "1st", "2nd", "3rd", "Out"
    last_active:       str = ""    # "Active today", "2 weeks ago"
    profile_picture:   str = ""
    connection_count: int = 0

    # ── Scraping metadata ──────────────────────────────────────
    scraped_at:       str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    source_keyword:   str = ""
    source_country:   str = ""

    # ── Helpers ────────────────────────────────────────────────

    @property
    def has_email(self) -> bool:
        return bool(self.email and self.email not in ("", "N/A"))

    @property
    def has_phone(self) -> bool:
        return bool(self.phone and self.phone not in ("", "N/A"))

    @property
    def has_resume(self) -> bool:
        return bool(self.resume_url and self.resume_url not in ("", "N/A"))

    @property
    def contact_score(self) -> int:
        """Score 0-5 based on how much contact info we have."""
        score = 0
        if self.has_email:
            score += 2
        if self.has_phone:
            score += 1
        if self.has_resume:
            score += 1
        if self.twitter:
            score += 0.5
        if self.website:
            score += 0.5
        return int(score)

    def to_dict(self) -> dict:
        return {
            "linkedin_url":            self.linkedin_url,
            "profile_id":              self.profile_id,
            "full_name":               self.full_name,
            "headline":                self.headline,
            "location":                self.location,
            "country":                 self.country,
            "country_code":            self.country_code,
            "current_title":           self.current_title,
            "current_company":         self.current_company,
            "current_company_industry": self.current_company_industry,
            "experience_years":        self.experience_years,
            "seniority_level":         self.seniority_level,
            "email":                   self.email,
            "phone":                   self.phone,
            "twitter":                 self.twitter,
            "website":                 self.website,
            "resume_url":              self.resume_url,
            "summary":                 self.summary,
            "skills":                  ", ".join(self.skills),
            "certifications":          ", ".join(self.certifications),
            "languages":               ", ".join(self.languages),
            "connection_degree":       self.connection_degree,
            "last_active":             self.last_active,
            "scraped_at":              self.scraped_at,
            "source_keyword":          self.source_keyword,
            "source_country":           self.source_country,
            "contact_score":           self.contact_score,
        }
