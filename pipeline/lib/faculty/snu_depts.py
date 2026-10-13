"""서울대학교 화학부 · 물리천문학부 · 수리과학부 · 컴퓨터공학부.

화학부 and 물리천문학부 share one CMS (research-faculty/faculty/fulltime, Korean and English pages with
the same profidx); 수리과학부 and 컴퓨터공학부 run their own sites.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, flip_comma_name, soup, text


# ------------------------------------------------------------------ 화학부 · 물리천문학부 (shared CMS)
def parse_cms_list(html: str, base_url: str) -> dict[str, dict]:
    """profidx -> {name, position_raw, url}; the name link holds the position in a child <span>/<em>."""
    s = soup(html)
    out: dict[str, dict] = {}
    for a in s.select("a[href*='profidx=']"):
        m = re.search(r"profidx=(\d+)", a["href"])
        pos_el = a.find(["span", "em"])
        pos = text(pos_el)
        if pos_el:
            pos_el.extract()
        name = text(a)
        if not m or not name or m.group(1) in out:
            continue
        out[m.group(1)] = {"name": name, "position_raw": pos, "url": urljoin(base_url, a["href"])}
    return out


def collect_cms(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    ehtml, eurl, _ = client.get_html(dept.options["eng_url"])
    en = parse_cms_list(ehtml, eurl)
    records = []
    for pid, r in parse_cms_list(html, url).items():
        e = en.get(pid, {})
        records.append(FacultyRecord(
            univ=dept.univ, dept=dept.code, name_ko=r["name"], name_en=flip_comma_name(e.get("name")),
            position_raw=r["position_raw"], position=normalize_position(r["position_raw"]),
            is_full_time=True,  # page = 교수 (full-time); visiting/emeritus are separate pages
            faculty_list_url=url, faculty_page_url=r["url"], retrieved_at=day,
        ))
    return records


# ------------------------------------------------------------------ 수리과학부
def parse_math_list(html: str, base_url: str) -> list[dict]:
    """Cards: "강명주(Myung-ju Kang)" + position tag, mailto and homepage links, field tags."""
    s = soup(html)
    out, seen = [], set()
    for item in s.select("div.item"):
        cap = item.select_one("div.item-caption")
        h4 = cap.select_one("h4") if cap else None
        if not h4:
            continue
        pos_el = h4.select_one("span")
        pos = text(pos_el)
        if pos_el:
            pos_el.extract()
        raw = text(h4) or ""
        m = re.match(r"^([가-힣\s]+?)\s*\((.*)\)\s*$", raw)
        name_ko, name_en = (m.group(1).strip(), m.group(2).strip()) if m else (raw, None)
        if (name_ko, name_en) in seen:
            continue
        seen.add((name_ko, name_en))
        mail = cap.select_one("a[href^='mailto:']")
        home = cap.select_one("a[href^='http']")
        out.append({"name_ko": name_ko, "name_en": flip_comma_name(name_en), "position_raw": pos,
                    "email": clean_email(mail["href"]) if mail else None,
                    "homepage_url": abs_url(base_url, home["href"]) if home else None,
                    "fields": [t for t in (text(x) for x in cap.select("li span.tack-icon")) if t]})
    return out


def collect_math(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [FacultyRecord(
        univ=dept.univ, dept=dept.code, name_ko=r["name_ko"], name_en=r["name_en"],
        position_raw=r["position_raw"], position=normalize_position(r["position_raw"]), is_full_time=True,
        homepage_url=r["homepage_url"], email=r["email"], research_fields=r["fields"],
        faculty_list_url=url, faculty_page_url=url, retrieved_at=day,
    ) for r in parse_math_list(html, url)]


# ------------------------------------------------------------------ 컴퓨터공학부
def parse_cse_list(html: str, base_url: str) -> dict[str, dict]:
    """id -> card. The name comes from the link's aria-label ("강유 교수 상세 페이지로 이동"); the card text
    holds position, lab, phone and e-mail. Professors whose primary appointment is another department
    are marked "겸무" (Korean page) / "Adjunct" (English page)."""
    s = soup(html)
    out: dict[str, dict] = {}
    for art in s.select("article"):
        a = art.select_one("a[aria-label][href*='/people/faculty/']")
        if not a:
            continue
        m = re.search(r"/people/faculty/(\d+)", a["href"])
        name = re.sub(r"\s*교수\s*상세 페이지로 이동\s*$", "", a["aria-label"]).strip()
        body = text(art.select_one("div.break-keep")) or ""
        rest = body[len(name):].strip() if body.startswith(name) else body
        pos = rest.split(" ", 1)[0].rstrip(",") if rest else None
        mail = re.search(r"[\w.+-]+@[\w.-]+\.\w+", body)
        note = re.split(r"\s\(0\d", rest)[0].strip()  # drop phone numbers and e-mail
        out[m.group(1)] = {"name": name, "position_raw": pos, "note": note[:120],
                           "adjunct": bool(re.search(r"겸무|Adjunct", rest)),
                           "email": clean_email(mail.group(0)) if mail else None,
                           "url": urljoin(base_url, a["href"])}
    return out


def collect_cse(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    ehtml, eurl, _ = client.get_html(dept.options["eng_url"])
    en = parse_cse_list(ehtml, eurl)
    records = []
    for pid, r in parse_cse_list(html, url).items():
        e = en.get(pid, {})
        records.append(FacultyRecord(
            univ=dept.univ, dept=dept.code, name_ko=r["name"], name_en=e.get("name"),
            position_raw=r["note"] or r["position_raw"], position=normalize_position(r["position_raw"]),
            is_full_time=not r["adjunct"], email=r["email"],
            faculty_list_url=url, faculty_page_url=r["url"], retrieved_at=day,
        ))
    return records
