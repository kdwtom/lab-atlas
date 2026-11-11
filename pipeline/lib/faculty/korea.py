"""고려대학교 (안암) 생명과학부 · 화학과 · 물리학과 · 수학과 · 컴퓨터학과.

All five run the university CMS: a card per professor (div.pro_list / div.pro_list_box > dl) with the name in
<dt> ("강세종 Kahng, Se-Jong", "강태호 교수" or "고영규") and loosely labelled <dd> rows. The list is paginated;
articleLimit=200 returns everyone on one page.
"""
from __future__ import annotations

import re
from typing import Optional

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, flip_comma_name, soup, text

ALL = {"articleLimit": 200, "article.offset": 0}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"https?://\S+")
POSITION = re.compile(r"(조교수|부교수|교수|Assistant Professor|Associate Professor|Professor)")


def split_dt(raw: str) -> tuple[Optional[str], Optional[str]]:
    raw = re.sub(r"\s*(교수|부교수|조교수)\s*$", "", raw).strip()
    m = re.match(r"^([가-힣]{2,5})\s*(.*)$", raw)
    if not m:
        return None, flip_comma_name(raw) or None
    return m.group(1), flip_comma_name(m.group(2)) or None


def parse(html: str, base_url: str) -> list[dict]:
    out, seen = [], set()
    for dl in soup(html).select("div.pro_list dl, div.pro_list_box dl"):
        name_ko, name_en = split_dt(text(dl.select_one("dt")) or "")
        if not (name_ko or name_en) or (name_ko, name_en) in seen:
            continue
        seen.add((name_ko, name_en))
        rows = [text(d) or "" for d in dl.select("dd")]
        pos = email = home = lab = None
        fields: list[str] = []
        for r in rows:
            body = re.sub(r"^[^:]{1,12}:\s*", "", r).strip()          # drop "직위:", "연구분야 :", ...
            if re.match(r"^(연구분야|전공분야)", r):
                body = re.sub(r"^(연구분야|전공분야)\s*:?\s*", "", r)
                # degree at the end: "세포생물학, 텍사스대(1994)", "식물다양성·생태·진화 (University of California, 2014)"
                body = re.sub(r"\s*\([^()]*\d{4}\)\s*$", "", body)
                body = re.sub(r",\s*[^,]*(?:대학?|University|College|Institute|KAIST|POSTECH)\s*$", "", body)
                fields = [f.strip() for f in re.split(r",|;|/", body) if f.strip()]
            elif EMAIL.search(r) and not email:
                email = clean_email(EMAIL.search(r).group(0))
            elif URL.search(r) and not home:
                home = URL.search(r).group(0)
            elif not pos and POSITION.fullmatch(body):
                pos = body
            elif not lab and re.search(r"연구실|[Ll]ab|Laboratory|Group|그룹", body):
                lab = body
        a = dl.find_parent("a")
        detail = abs_url(base_url, a["href"]) if a is not None and "mode=view" in (a.get("href") or "") else base_url
        out.append({"name_ko": name_ko, "name_en": name_en, "position_raw": pos, "email": email,
                    "homepage_url": home, "lab_name": lab, "research_fields": fields, "faculty_page_url": detail})
    return out


def collect(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url, params=ALL)
    list_url = dept.faculty_list_url
    return [FacultyRecord(univ=dept.univ, dept=dept.code, position=normalize_position(r["position_raw"]) or "교수",
                          is_full_time=True, faculty_list_url=list_url, retrieved_at=day, **r)
            for r in parse(html, url)]
