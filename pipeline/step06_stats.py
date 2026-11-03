"""Step 6 — summary statistics + excluded.csv."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict

from . import config
from .lib.io import read_json, read_jsonl, write_csv, write_json
from .lib.selection import is_senior

log = logging.getLogger(__name__)

REASON_KO = {
    "not_full_time": "전임교원 아님(교수진 페이지 직위 기준)",
    "no_candidate": "OpenAlex 후보 없음",
    "no_english_name_no_anchor": "영문명·대표논문 모두 없음",
    "affiliation_mismatch": "후보의 최근 소속 불일치",
    "name_mismatch": "후보 이름 불일치",
    "topic_mismatch": "후보 연구주제가 학과 분야 밖",
    "ambiguous_multiple_candidates": "후보 여러 명(동명이인 가능성)",
    "below_paper_threshold": "최근 5년 논문 수가 분야별 기준 미만",
    "manual_review": "수동 검토에서 믿을 만한 프로필을 찾지 못함",
}


def rule_ko(disc: config.Discipline) -> str:
    """Selection rule of a field, in Korean (stats.md, excluded.csv)."""
    if disc.position_agnostic:
        what = "저자 순서 무관 논문"
    elif disc.alphabetical_counts:
        what = "마지막/교신저자 또는 알파벳 순 저자(3인 이상) 논문"
    else:
        what = "마지막/교신저자 논문"
    tail = (", 학회 논문 포함" if "conference-paper" in disc.extra_work_types else "") + \
        (f", 저자 {disc.max_authors}명 이상 논문 제외" if disc.max_authors else "")
    return f"{what} {disc.min_papers}편 이상{tail}"


def run(client=None) -> dict:
    out = config.OUTPUT_DIR
    faculty = read_json(out / "faculty.json")
    matches = read_json(out / "matches.json")
    status = read_json(out / "lab_status.json")
    papers = read_jsonl(out / "papers_raw.jsonl")
    errors = read_json(out / "faculty_errors.json") if (out / "faculty_errors.json").exists() else []
    status_by_aid = {(s["univ"], s["openalex_id"]): s for s in status}
    dept_of = config.DEPT_BY_CODE

    # ---------------------------------------------------------------- excluded.csv
    excluded = []
    for m in matches:
        if m["status"] == "excluded":
            excluded.append({
                "name_ko": m.get("name_ko") or "", "name_en": m.get("name_en") or "",
                "univ": m["univ"], "dept": m["dept"],
                "reason": m["reason"], "reason_ko": REASON_KO.get(m["reason"], ""),
                "detail": m.get("detail") or "",
                "candidate_ids": ";".join(c["openalex_id"] for c in m.get("candidates", [])),
                "faculty_page_url": m["faculty_page_url"],
            })
        else:
            s = status_by_aid.get((m["univ"], m["openalex_id"]))
            if s and not s["meets_criterion"]:
                excluded.append({
                    "name_ko": m.get("name_ko") or "", "name_en": m.get("name_en") or "",
                    "univ": m["univ"], "dept": m["dept"], "reason": "below_paper_threshold",
                    "reason_ko": f"최근 5년 {rule_ko(config.DISCIPLINES[s['discipline']])} 미충족",
                    "detail": f"senior papers {s['senior_paper_count_5y']} / all {s['paper_count_5y']}",
                    "candidate_ids": m["openalex_id"], "faculty_page_url": m["faculty_page_url"],
                })
    write_csv(out / "excluded.csv", excluded,
              ["name_ko", "name_en", "univ", "dept", "reason", "reason_ko", "detail", "candidate_ids",
               "faculty_page_url"])

    # ---------------------------------------------------------------- funnel per department
    funnel = []
    for d in config.DEPARTMENTS:
        fac = [f for f in faculty if f["dept"] == d.code]
        ms = [m for m in matches if m["dept"] == d.code]
        st = [s for s in status if d.code in s["depts"]]
        funnel.append({
            "univ": d.univ, "code": d.code, "discipline": d.discipline,
            "dept": f"{d.univ_name_ko} {d.dept_name_ko}",
            "listed": len(fac), "full_time": sum(f["is_full_time"] for f in fac),
            "matched": sum(m["status"] == "matched" for m in ms),
            "matched_high": sum(m.get("confidence") == "high" for m in ms if m["status"] == "matched"),
            "meets_criterion": sum(s["meets_criterion"] for s in st),
            "blocked": any(e.get("dept", e["univ"]) == d.code for e in errors),
        })
    total = {k: sum(r[k] for r in funnel) for k in ("listed", "full_time", "matched", "matched_high", "meets_criterion")}

    # ---------------------------------------------------------------- abstracts
    keep = {s["lab_id"] for s in status if s["meets_criterion"]}
    kp = [p for p in papers if set(p["lab_ids"]) & keep]
    senior = [p for p in kp if any(is_senior(p, l) for l in p["lab_ids"] if l in keep)]
    abstracts = {
        "papers": len(kp), "with_abstract": sum(bool(p.get("abstract")) for p in kp),
        "senior_papers": len(senior), "senior_with_abstract": sum(bool(p.get("abstract")) for p in senior),
        "with_tldr": sum(bool(p.get("tldr")) for p in kp),
    }
    home = [p for p in kp if any(p["pi_roles"][l].get("at_home_institution", True)
                                 for l in p["lab_ids"] if l in keep)]
    abstracts["analysis_papers"] = len(home)
    abstracts["analysis_with_abstract"] = sum(bool(p.get("abstract")) for p in home)
    per_lab_senior_abs = sorted(s.get("home_senior_abstract_count", s["senior_abstract_count"])
                                for s in status if s["meets_criterion"])
    labs_lt3 = sum(1 for v in per_lab_senior_abs if v < 3)

    reasons = Counter(e["reason"] for e in excluded)
    by_univ_reason = defaultdict(Counter)
    for e in excluded:
        by_univ_reason[e["dept"]][e["reason"]] += 1

    stats = {
        "window": [config.YEAR_FROM, config.YEAR_TO], "min_senior_papers": config.MIN_SENIOR_PAPERS,
        "funnel": funnel, "total": total, "labs_total": sum(x["meets_criterion"] for x in status), "excluded_by_reason": dict(reasons),
        "excluded_by_dept_reason": {k: dict(v) for k, v in by_univ_reason.items()},
        "abstracts": abstracts, "labs_with_lt3_senior_abstracts": labs_lt3,
        "faculty_errors": [{"dept": e.get("dept", e["univ"]), "url": e["url"], "error": e["error"]} for e in errors],
        "rules": {k: rule_ko(v) for k, v in config.DISCIPLINES.items()},
    }
    write_json(out / "stats.json", stats)
    md = render_md(stats)
    (out / "stats.md").write_text(md, encoding="utf-8")
    print(md)
    return stats


def pct(a: int, b: int) -> str:
    return f"{(100 * a / b):.1f}%" if b else "-"


def render_md(s: dict) -> str:
    L = [f"# 데이터 수집 요약 (기간 {s['window'][0]}–{s['window'][1]})", "", "분야별 선정 기준:", ""]
    L += [f"- {config.DISCIPLINES[k].name_ko}: {v}" for k, v in s["rules"].items()]
    L += ["", "| 학과 | 분야 | 교수진 등재 | 전임 | 매칭 성공 (high) | 기준 충족 |", "|---|---|---:|---:|---:|---:|"]
    for r in s["funnel"]:
        flag = " ⚠️수집 실패" if r["blocked"] else ""
        L.append(f"| {r['dept']}{flag} | {config.DISCIPLINES[r['discipline']].name_ko} | {r['listed']} | {r['full_time']} | "
                 f"{r['matched']} ({r['matched_high']}) | {r['meets_criterion']} |")
    t = s["total"]
    L.append(f"| **합계** | | **{t['listed']}** | **{t['full_time']}** | **{t['matched']} ({t['matched_high']})** | "
             f"**{t['meets_criterion']}** |")
    L.append("")
    L.append("기준 충족 수는 학과별로 셉니다. 두 학과에 등재된 교수는 각 학과에 한 번씩 세지만 연구실은 하나입니다"
             f" (전체 연구실 {s['labs_total']}곳).")
    L += ["", "## 제외 사유별 건수", "", "| 사유 | 건수 |", "|---|---:|"]
    for k, v in sorted(s["excluded_by_reason"].items(), key=lambda x: -x[1]):
        L.append(f"| {REASON_KO.get(k, k)} (`{k}`) | {v} |")
    a = s["abstracts"]
    L += ["", "## 초록 보유율 (기준 충족 연구실의 논문)", "",
          f"- 전체 논문: {a['papers']}편 중 초록 {a['with_abstract']}편 ({pct(a['with_abstract'], a['papers'])})",
          f"- 마지막/교신저자 논문: {a['senior_papers']}편 중 초록 {a['senior_with_abstract']}편 ({pct(a['senior_with_abstract'], a['senior_papers'])})",
          f"- Semantic Scholar TLDR: {a['with_tldr']}편 ({pct(a['with_tldr'], a['papers'])})",
          f"- 분석용 논문(PI 소속이 현 기관 또는 미기재): {a['analysis_papers']}편 중 초록 {a['analysis_with_abstract']}편 "
          f"({pct(a['analysis_with_abstract'], a['analysis_papers'])}) — 병합 프로필의 동명이인 논문 배제용",
          f"- 대표 논문 후보(분석용 + 마지막/교신 + 초록)가 3편 미만인 연구실: {s['labs_with_lt3_senior_abstracts']}개"]
    if s["faculty_errors"]:
        L += ["", "## 수집이 막힌 학과", ""] + [f"- {e['dept']}: {e['error']} ({e['url']})" for e in s["faculty_errors"]]
    return "\n".join(L) + "\n"
