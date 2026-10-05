"""KAIST 생명과학과 — 전임교수 list + per-professor detail pages."""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, find_orcid, soup, text

DEPT = config.DEPT_BY_UNIV["kaist"]
DETAIL = "https://bio.kaist.ac.kr/doc/ko/selectDoc.do?docSeq={seq}&menuSeq=3344&bbsSeq=120"


def parse_list(html: str) -> list[dict]:
    s = soup(html)
    out = []
    for li in s.select("#prof ul.prof-list > li"):
        name = text(li.select_one(".prof-name"))
        if not name:
            continue
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", name)
        name_en, name_ko = (m.group(1), m.group(2)) if m else (name, None)
        a = li.select_one("a[onclick]")
        seq = None
        if a:
            mm = re.search(r"fn_selectDoc\('(\d+)'\)", a.get("onclick", ""))
            seq = mm.group(1) if mm else None
        email = None
        for item in li.select(".prof-info li"):
            t = text(item) or ""
            if t.lower().startswith("email"):
                email = clean_email(t.split(":", 1)[-1])
        out.append({
            "name_en": name_en.strip(" ,") or None,
            "name_ko": (name_ko or "").strip() or None,
            "position_raw": text(li.select_one(".prof-type")),
            "email": email,
            "seq": seq,
        })
    return out


def parse_detail(html: str, base_url: str) -> dict:
    s = soup(html)
    homepage = None
    a = s.select_one("#profile .h_page a[href]")
    if a:
        homepage = abs_url(base_url, a["href"])
    lab = None
    fields: list[str] = []
    for row in s.select("#profile .in_cont .row"):
        title = (text(row.select_one(".title")) or "").upper()
        if title.startswith("LAB"):
            div = row.find("div")
            lab = text(div)
        elif "RESEARCH" in title:
            fields = [t for t in (text(li) for li in row.select("li")) if t]
    h2 = s.select_one("#profile .in_txt h2")
    pos = text(h2.select_one("span")) if h2 else None
    return {"homepage_url": homepage, "lab_name": lab, "research_fields": fields,
            "position_raw": pos, "orcid": find_orcid(html)}


def collect(client) -> list[FacultyRecord]:
    html, url, day = client.get_html(DEPT.faculty_list_url)
    rows = parse_list(html)
    records = []
    for r in rows:
        detail_url = DETAIL.format(seq=r["seq"]) if r["seq"] else url
        d = {}
        if r["seq"]:
            dhtml, detail_url, day = client.get_html(detail_url)
            d = parse_detail(dhtml, detail_url)
        pos_raw = r["position_raw"] or d.get("position_raw")
        records.append(FacultyRecord(
            univ="kaist", name_ko=r["name_ko"], name_en=r["name_en"],
            position_raw=pos_raw, position=normalize_position(pos_raw),
            is_full_time=True,  # page = 전임교수 roster
            lab_name=d.get("lab_name"), homepage_url=d.get("homepage_url"), email=r["email"],
            orcid=d.get("orcid"), research_fields=d.get("research_fields", []),
            faculty_list_url=url, faculty_page_url=detail_url, retrieved_at=day,
        ))
    return records
