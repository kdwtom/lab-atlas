"""POSTECH 생명과학과 — university researcher directory filtered by department.

The department site (life.postech.ac.kr) was unreachable during development, so the official
university directory (www.postech.ac.kr 연구자 검색, 학과명=생명과학과) is used. It lists Korean names
only; English names are not available, so OpenAlex matching relies on the publications listed on
each researcher page (anchors).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, find_orcid, soup, text

DEPT = config.DEPT_BY_UNIV["postech"]
DEPT_NAME = "생명과학과"
PAGE = 12


def parse_list(html: str, base_url: str) -> tuple[list[dict], int]:
    s = soup(html)
    total = 0
    m = re.search(r"총\s*(\d+)\s*건", s.get_text(" "))
    if m:
        total = int(m.group(1))
    out = []
    for li in s.select(".thumb_board_list > ul > li"):
        a = li.select_one(".cont .top a[href]")
        dept = text(li.select_one("li.type1"))
        if not a or dept != DEPT_NAME:
            continue
        name = text(a.select_one(".tit")) or text(a)
        href = urljoin(base_url, a["href"])
        mid = re.search(r"[?&]id=([0-9a-f]+)", href)
        out.append({"name_ko": name, "id": mid.group(1) if mid else None})
    return out, total


def parse_detail(html: str, base_url: str) -> dict:
    s = soup(html)
    h3 = s.select_one(".con-box h3.name")
    pos = text(h3.select_one(".rea")) if h3 else None
    name = None
    if h3:
        for span in h3.select("span"):
            span.extract()
        name = text(h3)
    dept = text(s.select_one(".con-box li.ic01"))
    a = s.select_one(".con-box li.ic04 a[href]")
    homepage = abs_url(base_url, a["href"]) if a else None
    m = s.select_one(".con-box li.ic03 a[href]")
    email = clean_email(m["href"] if m else None)
    citations: list[str] = []
    con2 = s.select_one("#con2")
    if con2:
        for line in con2.get_text("\n").split("\n"):
            line = re.sub(r"\s+", " ", line).strip()
            if re.search(r"\((?:19|20)\d{2}\s*\)$", line):
                citations.append(line)
    return {"name_ko": name, "position_raw": pos, "dept": dept, "homepage_url": homepage,
            "email": email, "anchor_citations": citations, "orcid": find_orcid(html)}


def collect(client) -> list[FacultyRecord]:
    rows: list[dict] = []
    offset = 0
    list_url = DEPT.faculty_list_url
    while True:
        html, url, _ = client.get_html(list_url, params={"pager.offset": offset, "pagerLimit": PAGE})
        page_rows, total = parse_list(html, url)
        rows.extend(page_rows)
        offset += PAGE
        if not page_rows or offset >= total:
            break
    records, seen = [], set()
    for r in rows:
        if not r["id"] or r["id"] in seen:
            continue
        seen.add(r["id"])
        durl = ("https://www.postech.ac.kr/kor/research-industry-academia/researcher-search.do"
                f"?mode=view&id={r['id']}")
        dhtml, durl, day = client.get_html(durl)
        d = parse_detail(dhtml, durl)
        if d["dept"] and d["dept"] != DEPT_NAME:
            continue
        pos = normalize_position(d["position_raw"])
        records.append(FacultyRecord(
            univ="postech", name_ko=d["name_ko"] or r["name_ko"], name_en=None,
            position_raw=d["position_raw"], position=pos,
            # directory lists all researchers; full-time only if the title is 교수/부교수/조교수
            is_full_time=pos is not None,
            homepage_url=d["homepage_url"], email=d["email"], orcid=d["orcid"],
            anchor_citations=d["anchor_citations"],
            faculty_list_url=list_url, faculty_page_url=durl, retrieved_at=day,
        ))
    return records
