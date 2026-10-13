"""GIST 물리·광과학과 — WordPress (Elementor) page with one section per person.

Section text: "조병익 Cho, Byoung-Ick Lab. 고에너지밀도물리 연구실 Position. Professor(Chair of Department)
Email bicho@gist.ac.kr Tel ...". Faculty and staff share the page; only professor positions are kept.
"""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import clean_email, flip_comma_name, soup, text

PERSON = re.compile(r"^(?P<ko>[가-힣]{2,5})\s+(?P<en>[A-Z][A-Za-z\-]+\s*,\s*[A-Za-z][A-Za-z\- ]*?)\s+"
                    r"(?:Lab\.\s*(?P<lab>.*?)\s+)?Position\.\s*(?P<pos>.*?)\s+Email\s+(?P<mail>\S+@\S+)")
FULL_TIME = re.compile(r"^(?:Assistant |Associate )?Professor\b", re.I)


def parse_phys_list(html: str) -> list[dict]:
    s = soup(html)
    out = []
    for sec in s.select("section.faculty-staff-wrap"):
        m = PERSON.search(text(sec) or "")
        if not m:
            continue
        out.append({"name_ko": m.group("ko"), "name_en": flip_comma_name(m.group("en")),
                    "lab_name": (m.group("lab") or "").strip() or None, "position_raw": m.group("pos").strip(),
                    "email": clean_email(m.group("mail"))})
    return out


def collect_phys(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [FacultyRecord(
        univ=dept.univ, dept=dept.code, name_ko=r["name_ko"], name_en=r["name_en"],
        position_raw=r["position_raw"], position=normalize_position(r["position_raw"]),
        # "Professor(Lecture Professor)" is a teaching-only post
        is_full_time=bool(FULL_TIME.search(r["position_raw"])) and "Lecture" not in r["position_raw"],
        lab_name=r["lab_name"], email=r["email"],
        faculty_list_url=url, faculty_page_url=url, retrieved_at=day,
    ) for r in parse_phys_list(html)]
