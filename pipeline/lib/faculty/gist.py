"""GIST 생명과학과 — 전임교수 list (Korean + English rosters joined by e-mail) + detail pages."""
from __future__ import annotations

import re

from ... import config
from ...schemas import FacultyRecord
from ..names import clean_display_name, normalize_position
from .base import abs_url, clean_email, find_orcid, soup, text

DEPT = config.DEPT_BY_UNIV["gist"]
ENG_LIST = "https://life.gist.ac.kr/prog/gsMember/lifeeng/P/Faculty/sub05_01_01/list.do"
DETAIL = "https://life.gist.ac.kr/prog/gsPerson/life/P/view.do?personId={pid}"


def parse_list(html: str, base_url: str) -> list[dict]:
    s = soup(html)
    out = []
    for body in s.select(".card--body"):
        name = text(body.select_one("strong.ui-list__title"))
        if not name:
            continue
        info = {}
        for li in body.select("ul.list-1st li"):
            k, v = text(li.find("b")), text(li.find("i"))
            if k:
                info[k.upper()] = v
        pid = None
        a = body.select_one("a[onclick*=fn_search_detail]")
        if a:
            m = re.search(r"fn_search_detail\('([^']+)'\)", a["onclick"])
            pid = m.group(1) if m else None
        hp = body.select_one(".ui-list__button a.btn-danger[href]")
        out.append({
            "name": clean_display_name(re.sub(r"\(.*?\)", "", name)),
            "lab_name": info.get("LAB NAME"),
            "email": clean_email(info.get("E-MAIL")),
            "pid": pid,
            "homepage_url": abs_url(base_url, hp["href"]) if hp else None,
        })
    return out


def english_name(raw: str) -> str:
    """'KWON Yonghoon' -> 'Yonghoon Kwon'; western-order names are kept."""
    toks = raw.split()
    if len(toks) >= 2 and toks[0].isupper() and len(toks[0]) > 1:
        return " ".join(toks[1:] + [toks[0].capitalize()])
    return raw


def parse_detail(html: str) -> dict:
    s = soup(html)
    lines = [re.sub(r"\s+", " ", l).strip() for l in s.get_text("\n").split("\n")]
    lines = [l for l in lines if l]
    sections: dict[str, list[str]] = {}
    current = None
    heads = {"RESEARCH FIELD", "EDUCATION", "WORK EXPERIENCE", "REPRESENTATIVE_PUBLICATIONS",
             "REPRESENTATIVE PUBLICATIONS", "INTRODUCE", "WEBSITE"}
    for l in lines:
        if l.upper() in heads:
            current = l.upper().replace(" ", "_")
            sections[current] = []
        elif current:
            sections[current].append(l)
    pos = None
    for l in sections.get("WORK_EXPERIENCE", []):
        if re.search(r"present", l, re.I) and re.search(r"professor", l, re.I):
            m = re.search(r"((?:Assistant|Associate|Full)?\s*Professor)", l, re.I)
            pos = m.group(1).strip() if m else None
            break
    pubs = sections.get("REPRESENTATIVE_PUBLICATIONS", [])[:20]
    pubs = [p for p in pubs if re.search(r"(?:19|20)\d{2}", p)]
    return {"position_raw": pos, "research_fields": sections.get("RESEARCH_FIELD", [])[:10],
            "anchor_citations": pubs, "orcid": find_orcid(html)}


def collect(client) -> list[FacultyRecord]:
    html, url, _ = client.get_html(DEPT.faculty_list_url)
    ko = parse_list(html, url)
    ehtml, eurl, _ = client.get_html(ENG_LIST)
    en_by_email = {r["email"]: r["name"] for r in parse_list(ehtml, eurl) if r["email"]}
    records = []
    for r in ko:
        durl = DETAIL.format(pid=r["pid"]) if r["pid"] else url
        d = {}
        day = None
        if r["pid"]:
            dhtml, durl, day = client.get_html(durl)
            d = parse_detail(dhtml)
        en_raw = en_by_email.get(r["email"])
        records.append(FacultyRecord(
            univ="gist", name_ko=r["name"], name_en=english_name(en_raw) if en_raw else None,
            position_raw=d.get("position_raw"), position=normalize_position(d.get("position_raw")),
            is_full_time=True,  # page = 전임교수 roster
            lab_name=r["lab_name"], homepage_url=r["homepage_url"], email=r["email"],
            orcid=d.get("orcid"), research_fields=d.get("research_fields", []),
            anchor_citations=d.get("anchor_citations", []),
            faculty_list_url=url, faculty_page_url=durl, retrieved_at=day or _today(),
        ))
    return records


def _today():
    return config.TODAY
