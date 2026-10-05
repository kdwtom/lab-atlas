"""Spot check: compare N random labs with their live sources (stage 6).

    python -m pipeline.run --steps spotcheck            # 10 labs, seed 2026
    (env SPOTCHECK_N / SPOTCHECK_SEED override)

Per lab, everything is fetched live (no cache):
- 소속: the cited faculty page (detail page if we have one) still lists the PI's Korean or English name
- OpenAlex: author exists, ORCID matches, an affiliation with the university in the last 3 years
- 논문: each representative paper's OpenAlex record still lists the PI as an author, with the same DOI,
  year and title, and the PI role (last / corresponding) the site claims
- 논문 수: live OpenAlex count of article+review in the window, minus the namesake papers excluded after
  manual review (curation/excluded_papers.csv), vs the site
- 링크: homepage and faculty page respond
Writes docs/verification.md.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import random
import re
from collections import Counter
from datetime import date

from rapidfuzz import fuzz

from . import config
from .lib.io import read_json
from .lib.live import LiveClient, openalex_params

log = logging.getLogger(__name__)

OK, FAIL, WARN = "✅", "❌", "⚠️"


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def _oa(live: LiveClient, path: str, **params) -> dict | None:
    q = "&".join(f"{k}={v}" for k, v in openalex_params(**params).items())
    r = live.get(f"{config.OPENALEX_BASE}/{path}{'?' + q if q else ''}", keep_body=True)
    return json.loads(r.body) if r.status == 200 else None


def _check_affiliation(live: LiveClient, lab: dict) -> tuple[str, str]:
    detail = next((s["url"] for s in lab["sources"] if s["kind"] == "faculty_detail"), None)
    url = detail or lab["faculty_page_url"]
    r = live.get(url, keep_body=True)
    if r.status is None or r.status >= 400:
        return FAIL, f"교수진 페이지 응답 {r.status or r.error}"
    body = _norm(r.body)
    names = [n for n in (lab["pi_name_ko"], lab["pi_name_en"]) if n]
    hit = [n for n in names if _norm(n) in body]
    if not hit and lab["pi_name_en"]:  # "Lee, Byung-Hoon" / "LEE Byung Hoon" orderings
        toks = lab["pi_name_en"].lower().replace("-", " ").split()
        if toks and _norm(" ".join(toks[-1:] + toks[:-1])) in body:
            hit = [lab["pi_name_en"]]
    page = "상세" if detail else "목록"
    return (OK, f"{page} 페이지에 '{hit[0]}' 등재") if hit else (FAIL, f"{page} 페이지에서 이름을 찾지 못함")


def _check_author(live: LiveClient, lab: dict, inst_id: str) -> tuple[str, str]:
    a = _oa(live, f"authors/{lab['openalex_id']}")
    if not a:
        return FAIL, "OpenAlex 저자 조회 실패"
    notes, mark = [], OK
    orcid = (a.get("orcid") or "").rsplit("/", 1)[-1] or None
    if lab["orcid"] and orcid != lab["orcid"]:
        mark = FAIL
        notes.append(f"ORCID 불일치({orcid})")
    years = [y for aff in a.get("affiliations", []) if aff["institution"]["id"].endswith(inst_id)
             for y in aff.get("years", [])]
    recent = max(years) if years else None
    if not recent or recent < config.YEAR_TO - config.CURRENT_AFFILIATION_YEARS + 1:
        mark = FAIL
        notes.append(f"최근 소속 이력 없음(최근 {recent})")
    else:
        notes.append(f"소속 이력 ~{recent}")
    notes.insert(0, a["display_name"])
    return mark, ", ".join(notes)


def _check_papers(live: LiveClient, lab: dict, papers: dict[str, dict]) -> tuple[str, str]:
    ids = lab["representative_paper_ids"]
    if not ids:
        return WARN, "대표 논문 없음"
    if len(ids) > 1:  # one batched call for the lab's representative papers
        data = _oa(live, "works", filter="openalex:" + "|".join(ids), **{"per-page": 50})
        works = {w["id"].rsplit("/", 1)[-1]: w for w in (data or {}).get("results", [])}
    else:
        w = _oa(live, f"works/{ids[0]}")
        works = {ids[0]: w} if w else {}
    good, problems = 0, []
    for pid in ids:
        p, w = papers[pid], works.get(pid)
        if not w:
            problems.append(f"{pid} 조회 실패")
            continue
        issues = []
        mine = [a for a in w["authorships"] if (a["author"].get("id") or "").endswith(lab["openalex_id"])]
        if not mine:
            issues.append("PI 저자 아님")
        else:
            role = p["pi_roles"].get(lab["id"], {})
            last = mine[0]["author_position"] == "last"
            corr = bool(mine[0].get("is_corresponding"))
            if not (last or corr):
                issues.append("마지막/교신 아님")
            elif role and (role.get("position") == "last") != last:
                issues.append("저자 순서 변경")
        if (w.get("doi") or None) != p["doi"]:
            issues.append(f"DOI 불일치({w.get('doi')})")
        if w.get("publication_year") != p["year"]:
            issues.append(f"연도 {w.get('publication_year')}≠{p['year']}")
        if fuzz.ratio(_norm(w.get("title") or ""), _norm(p["title"])) < 90:
            issues.append("제목 불일치")
        if issues:
            problems.append(f"{pid}: {', '.join(issues)}")
        else:
            good += 1
    mark = OK if good == len(ids) else (WARN if good else FAIL)
    return mark, f"{good}/{len(ids)} 일치" + (f" — {'; '.join(problems)}" if problems else "")


def _excluded_counts() -> Counter:
    path = config.PIPELINE_DIR / "curation" / "excluded_papers.csv"
    if not path.exists():
        return Counter()
    with path.open(encoding="utf-8-sig") as f:
        return Counter(r["lab_id"] for r in csv.DictReader(f))


def _check_count(live: LiveClient, lab: dict, excluded: int) -> tuple[str, str]:
    data = _oa(live, "works", filter=f"author.id:{lab['openalex_id']},"
               f"publication_year:{config.YEAR_FROM}-{config.YEAR_TO},type:article|review", **{"per-page": 1})
    if not data:
        return FAIL, "조회 실패"
    n = data["meta"]["count"]
    site = lab["paper_count_5y"]
    text = f"사이트 {site} / OpenAlex 현재 {n}"
    if excluded:
        text += f" − 제외 {excluded} = {n - excluded}"
    mark = OK if n - excluded == site else (WARN if n - excluded > site else FAIL)
    return mark, text


def _check_links(live: LiveClient, lab: dict) -> tuple[str, str]:
    parts, mark = [], OK
    for label, url in (("홈페이지", lab["homepage_url"]), ("교수진", lab["faculty_page_url"])):
        if not url:
            parts.append(f"{label} 정보 없음")
            continue
        r = live.get(url)
        parts.append(f"{label} {r.status or 'ERR'}")
        if r.verdict in ("broken", "unreachable"):
            mark = FAIL
        elif r.verdict == "blocked" and mark == OK:
            mark = WARN
    return mark, " · ".join(parts)


def run(client=None) -> None:
    n = int(os.environ.get("SPOTCHECK_N", 10))
    seed = int(os.environ.get("SPOTCHECK_SEED", 2026))
    d = config.WEB_DATA_DIR
    labs = read_json(d / "labs.json")
    papers = {p["id"]: p for p in read_json(d / "papers.json")}
    inst = read_json(config.OUTPUT_DIR / "institutions.json")
    sample = random.Random(seed).sample(sorted(labs, key=lambda l: l["id"]), min(n, len(labs)))
    live = LiveClient(min_interval=1.0)
    excluded = _excluded_counts()

    checks = [("소속(교수진 페이지)", lambda l: _check_affiliation(live, l)),
              ("OpenAlex 저자", lambda l: _check_author(live, l, inst[l["univ"]]["id"])),
              ("대표 논문", lambda l: _check_papers(live, l, papers)),
              ("논문 수", lambda l: _check_count(live, l, excluded[l["id"]])),
              ("링크", lambda l: _check_links(live, l))]
    rows = []
    for lab in sample:
        res = [f(lab) for _, f in checks]
        rows.append((lab, res))
        log.info("%s %s: %s", lab["id"], lab["pi_name_ko"], " | ".join(f"{m} {t}" for m, t in res))

    md = ["# 무작위 연구실 10개 출처 대조", "",
          f"검사일 {date.today().isoformat()} · 표본 {len(sample)}개 (random seed {seed}) · "
          f"`python -m pipeline.run --steps spotcheck`로 재현. 모든 항목을 캐시 없이 실시간으로 조회했습니다.", "",
          "| 연구실 | " + " | ".join(c for c, _ in checks) + " |",
          "|---|" + "---|" * len(checks)]
    for lab, res in rows:
        who = f"{lab['pi_name_ko'] or lab['pi_name_en']} ({lab['univ_name_ko']})<br>`{lab['id']}`"
        md.append(f"| {who} | " + " | ".join(f"{m} {t}".replace("|", "/") for m, t in res) + " |")
    tally = {c: sum(r[i][0] == OK for _, r in rows) for i, (c, _) in enumerate(checks)}
    md += ["", "통과(✅) 수: " + ", ".join(f"{c} {k}/{len(rows)}" for c, k in tally.items()), "",
           "범례: ✅ 일치 · ⚠️ 부분 일치/수동 확인 필요(봇 차단 등) · ❌ 불일치.",
           "논문 수: OpenAlex 현재 값에서 사람이 검토해 제외한 동명이인 논문(`pipeline/curation/excluded_papers.csv`)을 뺀 값이 "
           "사이트 값과 같으면 ✅. 수집 이후 OpenAlex에 새 논문이 추가되면 ⚠️가 될 수 있습니다.", ""]
    out = config.ROOT / "docs" / "verification.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    log.info("wrote %s", out.relative_to(config.ROOT))
