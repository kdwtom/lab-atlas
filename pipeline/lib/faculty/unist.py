"""UNIST 생명과학과 — university researcher directory (학과=생명과학과) + research.unist.ac.kr profiles.

bio.unist.ac.kr was unreachable during development; the official university directory is used.
"""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, find_orcid, soup, text

DEPT = config.DEPT_BY_UNIV["unist"]
DEPT_NAME = "생명과학과"
PAGE = 8


def parse_list(html: str) -> tuple[list[dict], int]:
    s = soup(html)
    total = 0
    m = re.search(r"총\s*(\d+)\s*건", s.get_text(" "))
    if m:
        total = int(m.group(1))
    out = []
    for li in s.select(".bn-list-prog-researcher li"):
        a = li.select_one(".b-img-box a[href]")
        if not a:
            continue
        body = re.sub(r"\s+", " ", li.get_text(" ", strip=True))
        dm = re.search(r"학과\s*(\S+)", body)
        if not dm or dm.group(1) != DEPT_NAME:
            continue
        out.append({"name_ko": a.get("title", "").strip() or None, "detail_url": a["href"]})
    return out, total


def parse_detail(html: str, base_url: str) -> dict:
    s = soup(html)
    box = s.select_one(".researcher-box01") or s
    dept = text(box.select_one(".txt01"))
    name_ko = text(box.select_one(".txt02"))
    spans = [text(x) for x in box.select(".txt03 span")]
    pos = spans[0] if spans else None
    name_en = spans[1] if len(spans) > 1 else None
    homepage = None
    for a in box.select(".bn-link-box a[href]"):
        if "홈페이지" in (a.get("title", "") + (text(a) or "")):
            homepage = abs_url(base_url, a["href"])
    m = box.select_one(".ico-mail a[href]")
    return {"dept": dept, "name_ko": name_ko, "name_en": name_en, "position_raw": pos,
            "homepage_url": homepage, "email": clean_email(m["href"] if m else None),
            "orcid": find_orcid(html)}


def collect(client) -> list[FacultyRecord]:
    rows: list[dict] = []
    offset = 0
    while True:
        html, url, _ = client.get_html(DEPT.faculty_list_url, params={"pager.offset": offset})
        page_rows, total = parse_list(html)
        rows.extend(page_rows)
        offset += PAGE
        if not page_rows or offset >= total:
            break
    records, seen = [], set()
    for r in rows:
        if r["detail_url"] in seen:
            continue
        seen.add(r["detail_url"])
        dhtml, durl, day = client.get_html(r["detail_url"])
        d = parse_detail(dhtml, durl)
        if d["dept"] and d["dept"] != DEPT_NAME:
            continue
        pos = normalize_position(d["position_raw"])
        name_ko, name_en = d["name_ko"] or r["name_ko"], d["name_en"]
        if name_ko and not name_en and not re.search(r"[가-힣]", name_ko):  # foreign faculty: one Latin name
            name_ko, name_en = None, name_ko
        records.append(FacultyRecord(
            univ="unist", name_ko=name_ko, name_en=name_en,
            position_raw=d["position_raw"], position=pos, is_full_time=pos is not None,
            homepage_url=d["homepage_url"], email=d["email"], orcid=d["orcid"],
            faculty_list_url=DEPT.faculty_list_url, faculty_page_url=durl, retrieved_at=day,
        ))
    return records
