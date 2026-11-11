"""한양대학교 (서울) 생명과학과 · 화학과 · 물리학과 · 수학과 · 컴퓨터소프트웨어학부.

All five run the university Liferay site with one profile card per person (div.hyu-profile-inner): a heading
(h4) and a sub-heading holding the two names in either order, a description holding the position or the office,
and contact links (mail, homepage). Emeritus, visiting and research faculty share the page, so the card text
decides who is full-time.
"""
from __future__ import annotations

import re
from typing import Optional

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import clean_email, flip_comma_name, soup, text

HANGUL = re.compile(r"[가-힣]")
# teaching-track (교육전담, "Professor (teaching)") and joint appointments are left out like elsewhere (names.py)
NOT_FULL_TIME = re.compile(r"명예|초빙|객원|겸임|겸무|겸직|퇴임|퇴직|석좌|연구교수|강의|대우|교육전담|소속 및 직위|"
                           r"Emeritus|Honorary|Visiting|Adjunct|Research Prof|Lecturer|Teaching|Industry|산학|특임|"
                           r"Retired|Joint Appointment", re.I)
FIELD_DESC = re.compile(r"^(?:연구영역|연구분야)\s*[:\-]\s*")
POSITION = re.compile(r"(조교수|부교수|교수|Assistant Professor|Associate Professor|Professor)")


def clean_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = re.sub(r",?\s*Ph\.?\s*D\.?|\s*(교수|부교수|조교수)$", "", s).strip(" ,")
    return s or None


def parse(html: str, base_url: str) -> list[dict]:
    out, seen = [], set()
    for card in soup(html).select("div.hyu-profile-inner"):
        a = clean_name(text(card.select_one("h4")))
        b = clean_name(text(card.select_one("div.hyu-profile-info-title-position")))
        if not a:
            continue
        name_ko = next((x for x in (a, b) if x and HANGUL.search(x) and len(x) <= 5), None)
        name_en = next((x for x in (a, b) if x and not HANGUL.search(x)), None)
        if not (name_ko or name_en) or (name_ko, name_en) in seen:
            continue
        desc = text(card.select_one("div.hyu-profile-info-desc")) or ""
        head = " ".join(x for x in (a, b, desc) if x)
        if NOT_FULL_TIME.search(head):
            continue
        seen.add((name_ko, name_en))
        pos = POSITION.search(desc) or POSITION.search(b or "")
        links = card.select("ul.hyu-profile-info-contact a[href]")
        mail = next((x["href"] for x in links if x["href"].startswith("mailto:")), None)
        home = next((x["href"] for x in links if x["href"].startswith("http")), None)
        fields: list[str] = []
        if FIELD_DESC.match(desc):
            fields = [f.strip() for f in re.split(r",|;", FIELD_DESC.sub("", desc)) if f.strip()]
        elif desc and not re.search(r"Office|호|Professor|교수", desc):      # 컴퓨터소프트웨어학부: fields only
            fields = [desc]
        out.append({"name_ko": name_ko, "name_en": flip_comma_name(name_en), "position_raw": pos.group(1) if pos else None,
                    "email": clean_email(mail), "homepage_url": home, "research_fields": fields})
    return out


def collect(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [FacultyRecord(univ=dept.univ, dept=dept.code, position=normalize_position(r["position_raw"]) or "교수",
                          is_full_time=True, faculty_list_url=url, faculty_page_url=url, retrieved_at=day, **r)
            for r in parse(html, url)]
