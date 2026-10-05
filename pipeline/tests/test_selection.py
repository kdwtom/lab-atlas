from datetime import date

from pipeline.lib.selection import embedding_papers, representative_papers

TODAY = date(2026, 10, 4)
L = "snu-A1"


def paper(pid, year, cites, position="last", corr=False, home=True, abstract="text"):
    return {"id": pid, "year": year, "publication_date": f"{year}-03-01", "cited_by_count": cites,
            "abstract": abstract, "title": pid,
            "pi_roles": {L: {"position": position, "is_corresponding": corr, "at_home_institution": home}}}


def ids(ps):
    return [p["id"] for p in ps]


def test_ranked_by_citations_per_year_with_recent_paper():
    ps = [paper("old_hit", 2022, 400), paper("mid", 2023, 150), paper("older", 2022, 120),
          paper("recent", 2025, 5)]
    # 400/4.6, 150/3.6, 120/4.6 would fill all three slots; one recent paper must be included
    assert ids(representative_papers(ps, L, today=TODAY)) == ["old_hit", "mid", "recent"]


def test_candidates_need_senior_role_abstract_and_home_institution():
    ps = [paper("middle", 2025, 900, position="middle"), paper("no_abs", 2025, 800, abstract=None),
          paper("elsewhere", 2025, 700, home=False), paper("corr_first", 2024, 10, position="first", corr=True)]
    assert ids(representative_papers(ps, L, today=TODAY)) == ["corr_first"]


def test_embedding_prefers_senior_then_recent():
    ps = [paper("m26", 2026, 0, position="middle"), paper("s22", 2022, 0), paper("s25", 2025, 0),
          paper("x", 2026, 0, home=False)]
    assert ids(embedding_papers(ps, L, limit=3)) == ["s25", "s22", "m26"]
