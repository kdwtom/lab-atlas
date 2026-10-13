"""DGIST 화학 트랙 · 물리 트랙.

DGIST has no graduate chemistry or physics department; the undergraduate school's tracks list their
faculty (who hold appointments in various graduate departments). The chemistry track uses the DGIST CMS
(prog/trackProfsr); the physics track's official homepage is a Google Site linked from physics.dgist.ac.kr.
Both list English names only (physics adds the Korean name in parentheses).
"""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, flip_comma_name, soup, text

FULL_TIME = re.compile(r"^(?:Assistant |Associate )?Professor\b", re.I)


# ------------------------------------------------------------------ 화학 트랙 (DGIST CMS)
def parse_cms_track(html: str, base_url: str) -> list[dict]:
    s = soup(html)
    out = []
    for col in s.select("div.col"):
        title = text(col.select_one("strong.title"))
        if not title:
            continue
        name = re.sub(r",?\s*Ph\.?\s*D\.?\s*$", "", title).strip(" ,")
        home = col.select_one("a.home[href]")
        mail = col.select_one("a[href^='mailto:']")
        out.append({"name_en": flip_comma_name(name), "position_raw": text(col.select_one(".position")),
                    "lab_name": text(home.select_one(".link-text")) if home else None,
                    "homepage_url": abs_url(base_url, home["href"]) if home else None,
                    "email": clean_email(mail["href"]) if mail else None})
    return out


def collect_cms_track(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [FacultyRecord(
        univ=dept.univ, dept=dept.code, name_ko=None, name_en=r["name_en"],
        position_raw=r["position_raw"], position=normalize_position(r["position_raw"]),
        is_full_time=bool(FULL_TIME.search(r["position_raw"] or "")),
        lab_name=r["lab_name"], homepage_url=r["homepage_url"], email=r["email"],
        faculty_list_url=url, faculty_page_url=url, retrieved_at=day,
    ) for r in parse_cms_track(html, url)]


# ------------------------------------------------------------------ 물리 트랙 (Google Site)
PERSON = re.compile(
    r"(?P<en>[A-Z][A-Za-z\-]+\s*,\s*[A-Za-z][A-Za-z\-. ]*?)\s*(?:\(\s*(?P<ko>[가-힣]{2,5})\s*\))?\s*"
    r"(?P<pos>(?:Assistant |Associate |Adjunct |Concurrent |Visiting |Research )?Professor)\s*"
    r"(?:➕\s*(?P<lab>[^📝]*?))?\s*📝\s*(?P<mail>[\w.+-]+)\s*-at-\s*(?P<dom>[\w.-]+)")


def parse_site_track(html: str) -> list[dict]:
    t = re.sub(r"\s+", " ", soup(html).get_text(" ", strip=True))
    start = t.find(" Faculty ")
    end = t.find(" Staff ", start)
    t = t[start:end if end > 0 else None]
    out = []
    for m in PERSON.finditer(t):
        lab = (m.group("lab") or "").strip() or None
        out.append({"name_en": flip_comma_name(re.sub(r"\s+,", ",", m.group("en"))), "name_ko": m.group("ko"),
                    "position_raw": m.group("pos"), "lab_name": None if lab in (None, "ORCiD") else lab,
                    "email": clean_email(f"{m.group('mail')}@{m.group('dom')}")})
    return out


def collect_site_track(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [FacultyRecord(
        univ=dept.univ, dept=dept.code, name_ko=r["name_ko"], name_en=r["name_en"],
        position_raw=r["position_raw"], position=normalize_position(r["position_raw"]),
        is_full_time=bool(FULL_TIME.search(r["position_raw"])),
        lab_name=r["lab_name"], email=r["email"],
        faculty_list_url=url, faculty_page_url=url, retrieved_at=day,
    ) for r in parse_site_track(html)]
