"""DGIST 뉴바이올로지학과 — 교수 list; only cards labelled 전임교원 are kept."""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, soup, text

DEPT = config.DEPT_BY_UNIV["dgist"]


def parse_list(html: str, base_url: str) -> list[dict]:
    s = soup(html)
    out, seen = [], set()
    for col in s.select(".board--card--list .col"):
        btn = col.select_one("button.button_view")
        if not btn:
            continue
        title = text(btn.select_one("strong.title"))
        if not title:
            continue
        status = text(btn.select_one(".status"))
        if "/" in title:
            en, ko = [p.strip() for p in title.split("/", 1)]
        else:
            en, ko = None, title
        homepage = email = None
        for a in col.select(".link-wrap a[href]"):
            href = a["href"]
            if href.startswith("mailto:"):
                email = clean_email(href)
            else:
                homepage = homepage or abs_url(base_url, href)
        field = None
        for li in btn.select("li.info"):
            if "research" in (text(li.select_one(".tit")) or "").lower():
                field = text(li.select_one(".txt"))
        key = (ko, en)
        if key in seen:
            continue
        seen.add(key)
        out.append({"name_ko": ko, "name_en": en.replace(",", "") if en else None,
                    "status": status, "position_raw": text(btn.select_one(".position")),
                    "homepage_url": homepage, "email": email, "field": field})
    return out


def collect(client) -> list[FacultyRecord]:
    html, url, day = client.get_html(DEPT.faculty_list_url)
    records = []
    for r in parse_list(html, url):
        pos_raw = r["position_raw"]
        records.append(FacultyRecord(
            univ="dgist", name_ko=r["name_ko"], name_en=r["name_en"],
            position_raw=f"{r['status'] or ''} {pos_raw or ''}".strip() or None,
            position=normalize_position(pos_raw),
            is_full_time=(r["status"] == "전임교원"),
            homepage_url=r["homepage_url"], email=r["email"],
            research_fields=[r["field"]] if r["field"] else [],
            faculty_list_url=url, faculty_page_url=url, retrieved_at=day,
        ))
    return records
