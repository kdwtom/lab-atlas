"""서강대학교 수학과 · 물리학과 · 화학과 · 생명과학과 · 컴퓨터공학과.

Each department runs its own site (the university portal www.sogang.ac.kr is a JavaScript app without rosters):
  수학과      math.sogang.ac.kr      table rows, "김현석 교수" + contacts
  물리학과    physics.sogang.ac.kr   article.sgp-person cards with the English name in <small>
  화학과      chemistry.sogang.ac.kr li._prFlLi profile cards (rank, field, email)
  생명과학과  lifescien.sogang.ac.kr gnuboard list (bo_table=teacher = 전임교원); served over plain HTTP only
  컴퓨터공학과 computing.sogang.ac.kr Nuxt page; the professor list sits in the window.__NUXT__ payload
"""
from __future__ import annotations

import json
import re
from typing import Optional

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, flip_comma_name, soup, text

POSITION = re.compile(r"(조교수|부교수|교수|Assistant Professor|Associate Professor|Professor)")


def strip_title(name: Optional[str]) -> Optional[str]:
    """'김현석 교수' / '김 도 석' -> '김현석'."""
    if not name:
        return None
    name = re.sub(r"\s*(교수님?|부교수|조교수)\s*$", "", name).strip()
    if re.fullmatch(r"[가-힣](?:\s[가-힣]){1,4}", name):
        name = name.replace(" ", "")
    return name or None


def fields_of(s: Optional[str]) -> list[str]:
    return [f.strip() for f in re.split(r",|;|/|·", s or "") if f.strip()]


def record(dept: config.Department, day, list_url: str, **kw) -> FacultyRecord:
    kw.setdefault("faculty_page_url", list_url)
    if kw.get("name_ko") and not re.search(r"[가-힣]", kw["name_ko"]):   # "Stefano SCOPEL", "Hosuk Sean Lee"
        kw["name_en"] = kw.get("name_en") or kw["name_ko"]
        kw["name_ko"] = None
    return FacultyRecord(univ=dept.univ, dept=dept.code, position=normalize_position(kw.get("position_raw")) or "교수",
                         is_full_time=True, faculty_list_url=list_url, retrieved_at=day, **kw)


# ------------------------------------------------------------------ 수학과
def parse_math(html: str, base_url: str) -> list[dict]:
    out = []
    for tr in soup(html).select("div.objTag table tbody tr"):
        tds = tr.select("td")
        if len(tds) < 2:
            continue
        ps = [text(p) or "" for p in tds[0].select("p")]
        name = strip_title(ps[0] if ps else None)
        if not name:
            continue
        info = text(tds[1]) or ""
        mail = tr.select_one("a[href^='mailto:']")
        field = re.search(r"전공분야\s*:\s*(.+)$", info)
        detail = tr.select_one("a.new_win[href]")
        out.append({"name_ko": name, "position_raw": "교수", "email": clean_email(mail["href"]) if mail else None,
                    "research_fields": fields_of(field.group(1)) if field else [],
                    "faculty_page_url": abs_url(base_url, detail["href"]) if detail else base_url})
    return out


# ------------------------------------------------------------------ 물리학과
def parse_phys(html: str, base_url: str) -> list[dict]:
    out = []
    for card in soup(html).select("article.sgp-person"):
        h4 = card.select_one("h4")
        if not h4:
            continue
        small = h4.select_one("small")
        en = text(small)
        if small:
            small.extract()
        name = strip_title(text(h4))
        if not name:
            continue
        mail = card.select_one("a[href^='mailto:']")
        lab = card.select_one("dd a[href^='http']")
        out.append({"name_ko": name, "name_en": flip_comma_name(en.title()) if en else None,
                    "research_fields": [t for t in (text(li) for li in card.select("ul li.sgp-tag, ul[aria-label] li")) if t],
                    "email": clean_email(mail["href"]) if mail else None,
                    "homepage_url": lab["href"] if lab else None,
                    "lab_name": re.sub(r"\s*↗\s*$", "", text(lab) or "") or None if lab else None})
    return out


# ------------------------------------------------------------------ 화학과
def parse_chem(html: str, base_url: str) -> list[dict]:
    out = []
    for li in soup(html).select("li._prFlLi"):
        name = strip_title(text(li.select_one("div.prfl-name strong")))
        if not name:
            continue
        info = {text(dl.select_one("dt")) or "": dl.select_one("dd") for dl in li.select("div.artclInfo dl")}
        rank = text(info.get("직위(직급)")) or text(li.select_one("div.prof-rank"))
        mail = li.select_one("a[href^='mailto:']")
        out.append({"name_ko": name, "position_raw": rank, "research_fields": fields_of(text(info.get("연구분야"))),
                    "email": clean_email(mail["href"]) if mail else None})
    return out


# ------------------------------------------------------------------ 생명과학과
def parse_life(html: str, base_url: str) -> list[dict]:
    out = []
    for box in soup(html).select("div.box"):
        name = strip_title(text(box.select_one("p.name")))
        if not name:
            continue
        info = {re.sub(r"\s+", "", text(dl.select_one("dt")) or ""): text(dl.select_one("dd")) for dl in box.select("dl")}
        more = box.select_one("a.more[href]") or box.select_one("p.thumb a[href]")
        out.append({"name_ko": name, "lab_name": info.get("연구실"), "research_fields": fields_of(info.get("전공")),
                    "faculty_page_url": abs_url(base_url, more["href"]) if more else base_url})
    return out


# ------------------------------------------------------------------ 컴퓨터공학과 (Nuxt payload)
def nuxt_professors(html: str) -> list[dict]:
    """Professor objects from window.__NUXT__=(function(params){...}(args)). Values that are parameter names are
    looked up in the argument list, which is plain JSON apart from `void 0`."""
    m = re.search(r"window\.__NUXT__=\(function\(([^)]*)\)\{(.*)\}\((.*)\)\);?</script>", html, re.S)
    if not m:
        return []
    env = dict(zip(m.group(1).split(","), json.loads("[" + m.group(3).replace("void 0", "null") + "]")))

    def val(o: str, k: str):
        mm = re.search(k + r':("(?:[^"\\]|\\.)*"|[\w$]+)', o)
        if not mm:
            return None
        v = mm.group(1)
        return json.loads(v) if v.startswith('"') else env.get(v)

    keys = ("PROF_NM", "PROF_SE_NM", "EML_ADDR", "MJR_FLD_NM", "LAB_NM", "HMPG_URL_ADDR", "PROF_INFO_OTPT_SE_CD",
            "EDC_DEPT_PROF_GRP_SN")
    return [{k: val(o, k) for k in keys} for o in re.findall(r"\{[^{}]*PROF_NM:[^{}]*\}", m.group(2))]


def parse_cs(html: str, base_url: str) -> list[dict]:
    out, seen = [], set()
    profs = nuxt_professors(html)
    # PROF_SE_NM: 교수 (full-time) | 명예교수 | 겸임교수 | 산학협력중점. A retired professor in the emeritus group can
    # still say 교수, so whole groups holding any 명예교수 are left out.
    emeritus = {p["EDC_DEPT_PROF_GRP_SN"] for p in profs if p["PROF_SE_NM"] == "명예교수"}
    for p in profs:
        if (p["PROF_SE_NM"] != "교수" or p["EDC_DEPT_PROF_GRP_SN"] in emeritus or not p["PROF_NM"]
                or p["PROF_NM"] in seen):
            continue
        seen.add(p["PROF_NM"])
        out.append({"name_ko": p["PROF_NM"], "email": clean_email(p["EML_ADDR"]), "lab_name": p["LAB_NM"],
                    "homepage_url": p["HMPG_URL_ADDR"], "research_fields": fields_of(p["MJR_FLD_NM"])})
    return out


PARSE = {"math": parse_math, "phys": parse_phys, "chem": parse_chem, "life": parse_life, "cs": parse_cs}


def collect(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [record(dept, day, url, **r) for r in PARSE[dept.discipline](html, url)]
