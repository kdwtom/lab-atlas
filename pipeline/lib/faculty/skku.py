"""성균관대학교 생명과학과 · 화학과 · 물리학과 · 수학과 (자연과학캠퍼스) · 소프트웨어학과.

The college site (cscience.skku.edu) and the software site share one card format (div.faculty-info-box):
position and field in the first list item, the Korean name and lab in the second, contacts in the next <dd>.
Cards hold no English name. The list may be paginated (article.offset); a large articleLimit returns all.
"""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, soup, text

ALL = {"articleLimit": 200, "article.offset": 0}
NOT_FULL_TIME = re.compile(r"명예|초빙|겸임|겸무|겸직|석좌|연구교수|강의|대우|교육|산학|특임|Emeritus|Visiting|Adjunct", re.I)


def parse(html: str, base_url: str) -> list[dict]:
    out, seen = [], set()
    for box in soup(html).select("div.faculty-info-box"):
        lis = box.select("dl > dd:nth-of-type(1) li")
        if len(lis) < 2:
            continue
        pos = text(lis[0].select_one("span.jg"))
        field = text(lis[0].select_one("span.dtj"))
        name = text(lis[1].find("span", recursive=False))
        if not name or name in seen or NOT_FULL_TIME.search(pos or ""):
            continue
        seen.add(name)
        lab_el = lis[1].select_one("div.lab-div")
        lab_link = lab_el.select_one("a[href]") if lab_el else None
        home = lab_link or lis[1].find("a", href=True, recursive=False)
        mail = box.select_one("a[href^='mailto:']")
        detail = box.select_one("a.faculty-link")
        out.append({"name_ko": re.sub(r"\s*\(.*?\)", "", name).strip(), "position_raw": pos,
                    "research_fields": [f.strip() for f in re.split(r",|;", field or "") if f.strip()],
                    "lab_name": text(lab_el.find("span")) if lab_el else None,
                    "homepage_url": abs_url(base_url, home["href"].strip()) if home else None,
                    "email": clean_email(mail["href"]) if mail else None,
                    "faculty_page_url": abs_url(base_url, detail["href"].strip().rstrip("&").strip()) if detail else base_url})
    return out


def collect(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url, params=ALL)
    return [FacultyRecord(univ=dept.univ, dept=dept.code, position=normalize_position(r["position_raw"]) or "교수",
                          is_full_time=True, faculty_list_url=dept.faculty_list_url, retrieved_at=day, **r)
            for r in parse(html, url)]
