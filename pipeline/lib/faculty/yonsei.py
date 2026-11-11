"""연세대학교 (신촌) 시스템생물학과 · 생화학과 · 화학과 · 물리학과 · 수학과 · 컴퓨터과학과.

시스템생물학과, 생화학과 and 수학과 use the university CMS card list (div.board-faculty-box). The life-science
cards hold the Korean name only (detail pages need JavaScript); 수학과 cards hold both names. 화학과, 물리학과 and
컴퓨터과학과 run their own sites.
"""
from __future__ import annotations

import re
from typing import Optional

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, flip_comma_name, soup, text

HANGUL = re.compile(r"[가-힣]")
GENERIC_LINK = re.compile(r"personal|website|webpage|homepage|faculty information|more information|홈페이지", re.I)


def record(dept: config.Department, day, list_url: str, **kw) -> FacultyRecord:
    pos = kw.pop("position_raw", None)
    kw.setdefault("faculty_page_url", list_url)
    return FacultyRecord(univ=dept.univ, dept=dept.code, position_raw=pos, position=normalize_position(pos) or "교수",
                         is_full_time=True, faculty_list_url=list_url, retrieved_at=day, **kw)


def strip_role(name: Optional[str]) -> Optional[str]:
    """'노재석(학과장)' / '황성재 (인공지능학과장)' -> the name alone."""
    return re.sub(r"\s*\(.*?\)\s*", "", name).strip() or None if name else None


def split_names(a: Optional[str], b: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Two strings, one Korean and one English, in either order -> (name_ko, name_en)."""
    a, b = strip_role(a), strip_role(b)
    ko = next((x for x in (a, b) if x and HANGUL.search(x)), None)
    en = next((x for x in (a, b) if x and not HANGUL.search(x)), None)
    return ko, flip_comma_name(en)


# ------------------------------------------------------------------ university CMS cards
def parse_cards(html: str, base_url: str) -> list[dict]:
    out = []
    for box in soup(html).select("div.board-faculty-box"):
        dl = box.select_one("dl")
        if not dl:
            continue
        dt = text(dl.select_one("dt"))
        span = dl.select_one("dd span")
        sp = text(span)
        # 수학과: "김세익 (학과장)" in the span is the Korean name with a role; elsewhere the span is the position
        if sp and HANGUL.search(sp) and not re.search(r"교수", sp):
            name_ko, name_en = split_names(dt, sp)
            pos = None
        else:
            name_ko, name_en = split_names(dt, None)
            pos = sp
        if not (name_ko or name_en):
            continue
        mail = dl.select_one("a[href^='mailto:']")
        home = next((a for a in dl.select("a[href]") if a["href"].startswith("http")), None)
        detail = dl.select_one("a[href*='mode=view']")
        dds = [text(d) for d in dl.select("dd") if not d.select("a, span")]   # plain text rows only
        lab = text(home) if home is not None and not GENERIC_LINK.search(text(home) or "") else None
        fields = []
        if dds and dds[-1] and not re.search(r"\d{3,}|\d+호|Tel", dds[-1]):
            fields = [f.strip() for f in re.split(r",|;", dds[-1]) if f.strip()]
        out.append({"name_ko": name_ko, "name_en": name_en, "position_raw": pos,
                    "email": clean_email(mail["href"]) if mail else None,
                    "homepage_url": abs_url(base_url, home["href"]) if home is not None else None,
                    "lab_name": lab.lstrip("🌐").strip() if lab else None, "research_fields": fields,
                    "faculty_page_url": abs_url(base_url, detail["href"]) if detail else base_url})
    return out


def collect_cards(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [record(dept, day, url, **r) for r in parse_cards(html, url)]


# ------------------------------------------------------------------ 화학과
def parse_chem(html: str, base_url: str) -> list[dict]:
    out = []
    for item in soup(html).select("div.team-item"):
        name = text(item.select_one("h5"))
        if not name:
            continue
        mail = item.select_one("a[href^='mailto:']")
        home = item.select_one("a[href^='http']")
        name_ko, name_en = split_names(name, None)
        out.append({"name_ko": name_ko, "name_en": name_en, "position_raw": text(item.select_one("div.p-4 span")),
                    "email": clean_email(mail["href"]) if mail else None,
                    "homepage_url": abs_url(base_url, home["href"]) if home else None})
    return out


def collect_chem(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [record(dept, day, url, **r) for r in parse_chem(html, url)]


# ------------------------------------------------------------------ 물리학과 (list + detail pages)
def parse_phys_list(html: str, base_url: str) -> list[dict]:
    out = []
    for li in soup(html).select("ul.ul_pf li.item"):
        a = li.select_one("a.wrapper")
        name = text(li.select_one("strong.name"))
        if a and name:
            out.append({"name_ko": name, "field": text(li.select_one("span.area")), "url": abs_url(base_url, a["href"])})
    return out


def parse_phys_detail(html: str) -> dict:
    t = re.sub(r"\s+", " ", soup(html).get_text(" ", strip=True))
    en = re.search(r"(?:Professor|교수)\s+([A-Z][A-Za-z\-']+,\s*[A-Z][A-Za-z\-' ]+?)\s+연구분야", t)
    pos = re.search(r"(조교수|부교수|교수)\s+(?:Assistant |Associate )?Professor", t)
    mail = re.search(r"이메일\s+([\w.+-]+@[\w.-]+)", t)
    home = re.search(r"홈페이지\s+(https?://\S+)", t)
    return {"name_en": flip_comma_name(en.group(1)) if en else None, "position_raw": pos.group(1) if pos else None,
            "email": clean_email(mail.group(1)) if mail else None, "homepage_url": home.group(1) if home else None}


def collect_phys(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    out = []
    for r in parse_phys_list(html, url):
        d = parse_phys_detail(client.get_html(r["url"])[0])
        out.append(record(dept, day, url, name_ko=r["name_ko"], name_en=d["name_en"], position_raw=d["position_raw"],
                          email=d["email"], homepage_url=d["homepage_url"], faculty_page_url=r["url"],
                          research_fields=[r["field"]] if r["field"] else []))
    return out


# ------------------------------------------------------------------ 컴퓨터과학과
def parse_cs(html: str, base_url: str) -> list[dict]:
    out = []
    for tr in soup(html).select("table.yonsei-table tbody tr"):
        tds = tr.select("td")
        if len(tds) < 3:
            continue
        name = text(tds[1])
        if not name or not HANGUL.search(name):
            continue
        home = tr.select_one("a[href^='http']")
        out.append({"name_ko": strip_role(name), "research_fields": [f.strip() for f in (text(tds[2]) or "").split(",") if f.strip()],
                    "homepage_url": abs_url(base_url, home["href"]) if home else None,
                    "lab_name": text(home) if home else None})
    return out


def collect_cs(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [record(dept, day, url, **r) for r in parse_cs(html, url)]
