"""KAIST 화학과 · 물리학과 · 수리과학과 · 전산학부 — each department runs its own site."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ... import config
from ...schemas import FacultyRecord
from ..names import normalize_position
from .base import abs_url, clean_email, find_orcid, flip_comma_name, soup, text


# ------------------------------------------------------------------ 화학과
def parse_chem_list(html: str, base_url: str) -> list[dict]:
    """Cards: name, position, lab; the Korean and English pages share the /faculty/view/id/<n> ids."""
    s = soup(html)
    out = []
    for a in s.select("a[href*='faculty/view/id/']"):
        cap = a.select_one("figcaption.professor-list-info")
        if not cap:
            continue
        m = re.search(r"/view/id/(\d+)", a["href"])
        out.append({"id": m.group(1) if m else None,
                    "name": text(cap.select_one(".professor-list-info-overview-name")),
                    "position_raw": text(cap.select_one(".professor-list-info-position")),
                    "lab_name": text(cap.select_one(".professor-list-info-lab")),
                    "url": urljoin(base_url, a["href"])})
    return out


def collect_chem(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    ehtml, eurl, _ = client.get_html(dept.options["eng_url"])
    en = {r["id"]: r for r in parse_chem_list(ehtml, eurl)}
    records = []
    for r in parse_chem_list(html, url):
        e = en.get(r["id"], {})
        records.append(FacultyRecord(
            univ=dept.univ, dept=dept.code, name_ko=r["name"],
            name_en=flip_comma_name(e.get("name")), position_raw=r["position_raw"],
            position=normalize_position(r["position_raw"]), is_full_time=True,  # page = 교수진 (full-time)
            lab_name=e.get("lab_name") or r["lab_name"],
            faculty_list_url=url, faculty_page_url=r["url"], retrieved_at=day,
        ))
    return records


# ------------------------------------------------------------------ 물리학과
def parse_phys_list(html: str, base_url: str) -> list[dict]:
    """Rows: "Ahn, Jaewook (안재욱)" + position, e-mail "id(at)kaist.ac.kr", homepage, detail link."""
    s = soup(html)
    out = []
    for box in s.select("ul.text_area"):
        first = box.select_one("ul.text_box3 > li")
        if not first:
            continue
        pos = text(first.select_one("span"))
        raw = (text(first) or "").replace(pos or "", "").strip()
        m = re.match(r"^(.*?)\s*\(([가-힣\s]+)\)", raw)
        name_en, name_ko = (m.group(1), m.group(2).strip()) if m else (raw, None)
        body = box.get_text(" ", strip=True)
        em = re.search(r"E-mail\s*:\s*([\w.+-]+)\s*\(at\)\s*([\w.-]+)", body)
        hp = box.select_one("a.homepage[href]")
        det = box.select_one("a[href*='document_srl']")
        out.append({"name_en": flip_comma_name(name_en), "name_ko": name_ko, "position_raw": pos,
                    "email": clean_email(f"{em.group(1)}@{em.group(2)}") if em else None,
                    "homepage_url": abs_url(base_url, hp["href"]) if hp else None,
                    "url": det["href"] if det else base_url})
    return out


def collect_phys(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)  # category=193: Professor (full-time)
    return [FacultyRecord(
        univ=dept.univ, dept=dept.code, name_ko=r["name_ko"], name_en=r["name_en"],
        position_raw=r["position_raw"], position=normalize_position(r["position_raw"]), is_full_time=True,
        homepage_url=r["homepage_url"], email=r["email"],
        faculty_list_url=url, faculty_page_url=r["url"], retrieved_at=day,
    ) for r in parse_phys_list(html, url)]


# ------------------------------------------------------------------ 수리과학과
def parse_math_list(html: str, base_url: str) -> list[dict]:
    """Only the 전임교수 cards (class "prof"); "강문진 (Kang, Moon-Jin)" + rank, e-mail in the link title."""
    s = soup(html)
    out = []
    for card in s.select("div.person-item.prof"):
        h2 = card.select_one("h2")
        rank = h2.select_one(".rank") if h2 else None
        pos = text(rank)
        if rank:
            rank.extract()  # some cards have no name link, so the heading text would include the rank
        a = h2.select_one("a") if h2 else None
        raw = text(a) or text(h2) or ""
        m = re.match(r"^([가-힣\s]+?)\s*\((.*)\)\s*$", raw)
        name_ko, name_en = (m.group(1).strip(), m.group(2)) if m else (None, raw)
        mail = card.select_one("a.mailto-link[title]")
        home = card.select_one("a[href^='http']")
        out.append({"name_ko": name_ko, "name_en": flip_comma_name(name_en),
                    "position_raw": pos,
                    "email": clean_email(mail["title"]) if mail else None,
                    "homepage_url": abs_url(base_url, home["href"]) if home else None,
                    "field": text(card.select_one(".major"))})
    return out


def collect_math(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, day = client.get_html(dept.faculty_list_url)
    return [FacultyRecord(
        univ=dept.univ, dept=dept.code, name_ko=r["name_ko"], name_en=r["name_en"],
        position_raw=r["position_raw"], position=normalize_position(r["position_raw"]), is_full_time=True,
        homepage_url=r["homepage_url"], email=r["email"], research_fields=[r["field"]] if r["field"] else [],
        faculty_list_url=url, faculty_page_url=url, retrieved_at=day,
    ) for r in parse_math_list(html, url)]


# ------------------------------------------------------------------ 전산학부
CS_DETAIL = "https://cs.kaist.ac.kr/people/view?idx={idx}&kind=faculty&menu={menu}"


def parse_cs_list(html: str) -> list[dict]:
    """Only the first section ("교수"); later sections are KAIST/emeritus/adjunct/joint/visiting/research."""
    s = soup(html)
    head = next((p for p in s.select("p.line") if text(p) == "교수"), None)
    ul = head.find_next_sibling("ul") if head else None
    out = []
    for li in (ul.select("li.horiz_item") if ul else []):
        item = li.select_one("div.item[onclick]")
        m = re.search(r"facultyView\((\d+),\s*(\d+)\)", item["onclick"]) if item else None
        out.append({"name_ko": text(li.select_one("p.name")), "position_raw": text(li.select_one("p.depart")),
                    "field": text(li.select_one("p.part")),
                    "url": CS_DETAIL.format(idx=m.group(1), menu=m.group(2)) if m else None})
    return out


def parse_cs_detail(html: str, base_url: str) -> dict:
    t = re.sub(r"\s+", " ", soup(html).get_text(" ", strip=True))
    m = re.search(r"웹사이트\s+(https?://\S+)", t)
    # "... 교수연구실 N5, 2322 연구실 네트워크 보안 및 프라이버시 연구실 강민석 교수는 ..."
    tail = t[t.rfind("교수연구실") + len("교수연구실"):] if "교수연구실" in t else ""
    lab = re.search(r"\s연구실\s+(.+?)(?:\s+[가-힣]{2,4}\s+교수는|$)", tail)
    lab_name = lab.group(1).strip() if lab and len(lab.group(1)) <= 80 else None
    return {"homepage_url": abs_url(base_url, m.group(1)) if m else None,
            "lab_name": lab_name, "orcid": find_orcid(html)}


def collect_cs(client, dept: config.Department) -> list[FacultyRecord]:
    html, url, _ = client.get_html(dept.faculty_list_url)
    records = []
    for r in parse_cs_list(html):
        durl, d, day = r["url"] or url, {}, config.TODAY
        if r["url"]:
            dhtml, durl, day = client.get_html(r["url"])
            d = parse_cs_detail(dhtml, durl)
        records.append(FacultyRecord(
            univ=dept.univ, dept=dept.code, name_ko=r["name_ko"], name_en=None,
            position_raw=r["position_raw"], position=normalize_position(r["position_raw"]), is_full_time=True,
            lab_name=d.get("lab_name"), homepage_url=d.get("homepage_url"), orcid=d.get("orcid"),
            research_fields=[r["field"]] if r["field"] else [],
            faculty_list_url=url, faculty_page_url=durl, retrieved_at=day,
        ))
    return records
