"""서울대학교 생명과학부 — 현직교수 list + detail pages (with 주요논문)."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, find_orcid, soup, text

DEPT = config.DEPT_BY_UNIV["snu"]


def parse_list(html: str, base_url: str) -> list[dict]:
    s = soup(html)
    out, seen = [], set()
    for art in s.select("article.facultyitem"):
        a = art.select_one(".portfolio-desc h3 a[href]")
        if not a:
            continue
        href = urljoin(base_url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        out.append({
            "name_ko": text(a),
            "position_raw": text(art.select_one(".portfolio-desc h3 .ptit")),
            "detail_url": href,
        })
    return out


def parse_detail(html: str, base_url: str) -> dict:
    s = soup(html)
    h3 = s.select_one(".faculthead .heading-block h3")
    name_en = text(h3.select_one("span")) if h3 else None
    pos = text(s.select_one(".faculthead .heading-block .before-heading"))
    homepage = email = lab = None
    for li in s.select(".faculthead ul.prof li"):
        label = (text(li.find("span")) or "").lower()
        if label.startswith("website"):
            a = li.select_one("a[href]")
            homepage = abs_url(base_url, a["href"]) if a else None
        elif label.startswith("email"):
            a = li.select_one("a[href]")
            email = clean_email(a["href"] if a else None)
        elif label.startswith("lab"):
            # SNU's "Lab" row holds the lab phone number, not a lab name; keep only real names.
            value = (text(li) or "").split(":", 1)[-1].strip()
            lab = value if re.search(r"[A-Za-z가-힣]", value) else None
    fields = [t for t in (text(x) for x in s.select(".facultycontent .label")) if t]
    citations: list[str] = []
    for stit in s.select(".prof-stit"):
        if "논문" in (text(stit) or ""):
            wrap = stit.find_next_sibling(class_="prof-wrap")
            if wrap:
                citations = [t for t in (text(li) for li in wrap.select("li")) if t]
            break
    return {"name_en": name_en, "position_raw": pos, "homepage_url": homepage, "email": email,
            "lab_name": lab, "research_fields": fields, "anchor_citations": citations,
            "orcid": find_orcid(html)}


def collect(client) -> list[FacultyRecord]:
    html, url, _ = client.get_html(DEPT.faculty_list_url)
    records = []
    for r in parse_list(html, url):
        dhtml, durl, day = client.get_html(r["detail_url"])
        d = parse_detail(dhtml, durl)
        name_en = d["name_en"]
        if name_en and "," in name_en:  # "Kang, Chanhee" -> "Chanhee Kang"
            last, first = [p.strip() for p in name_en.split(",", 1)]
            name_en = f"{first} {last}".strip()
        pos_raw = d["position_raw"] or r["position_raw"]
        records.append(FacultyRecord(
            univ="snu", name_ko=r["name_ko"], name_en=name_en or None,
            position_raw=pos_raw, position=normalize_position(pos_raw), is_full_time=True,
            lab_name=d["lab_name"], homepage_url=d["homepage_url"], email=d["email"],
            orcid=d["orcid"], research_fields=d["research_fields"],
            anchor_citations=d["anchor_citations"],
            faculty_list_url=url, faculty_page_url=durl, retrieved_at=day,
        ))
    return records
