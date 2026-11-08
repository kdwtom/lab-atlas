"""Phase 1 (PLAN_PHASE1.md 0-8): department parsers, roster matching, field rules, joint appointments."""
from datetime import date

import numpy as np

from pipeline import config
from pipeline.lib.faculty import dgist_tracks, gist, gist_depts, kaist_depts, snu_depts
from pipeline.lib.faculty.base import flip_comma_name
from pipeline.lib.roster import Roster, compact
from pipeline.schemas import FacultyRecord, MatchResult
from pipeline.step03_match import apply_override, evaluate, field_share
from pipeline.similarity_audit import self_retrieval_rank
from pipeline.step04_papers import alphabetical, group_labs
from pipeline.trend import benjamini_hochberg, drop_outliers, map_place, shift_test, topic_shift
from pipeline.step08_analyze import band_cuts, closest_paper_pairs, similarity_band, split_cluster

INST = "I111"


# ------------------------------------------------------------------ parsers (fragments of the real pages, 2026-10)
def test_flip_comma_name():
    assert flip_comma_name("Kang, Jin Young") == "Jin Young Kang"
    assert flip_comma_name("Chang-Hee Cho") == "Chang-Hee Cho"
    assert flip_comma_name(None) is None


def test_kaist_phys_and_math():
    phys = """<ul class="text_area tpad_20"><li><a href="https://physics.kaist.ac.kr/index.php?document_srl=304">Further Info</a></li>
    <li><ul class="text_box3"><li>Ahn, Jaewook (안재욱) <span class="nomal_">Professor / KAIST Endowed Chair Professor</span></li>
    <li><strong>E-mail : </strong>jwahn(at)kaist.ac.kr</li><li><a class="homepage" href="http://qcl.kaist.ac.kr">x</a></li></ul></li></ul>"""
    r = kaist_depts.parse_phys_list(phys, "https://physics.kaist.ac.kr/")
    assert r[0]["name_en"] == "Jaewook Ahn" and r[0]["name_ko"] == "안재욱" and r[0]["email"] == "jwahn@kaist.ac.kr"
    math = """<div class="person-item col-md-3 prof"><h2><a href="https://x.org/">강문진 (Kang, Moon-Jin)</a>
    <span class="rank">부교수</span><a class="mailto-link" title="moonjinkang@kaist.ac.kr" href="javascript:;"></a></h2>
    <div class="major">비선형 편미분 방정식</div></div>
    <div class="person-item col-md-3 prof"><h2>박진형 (Park, Jinhyung) <span class="rank">부교수</span>
    <a class="mailto-link" title="parkjh13@kaist.ac.kr" href="javascript:;"></a></h2></div>
    <div class="person-item col-md-3 emer"><h2><a>고기형 (Ko, Ki Hyoung)</a><span class="rank">명예 교수</span></h2></div>"""
    r = kaist_depts.parse_math_list(math, "https://mathsci.kaist.ac.kr/")
    assert len(r) == 2 and r[0]["name_en"] == "Moon-Jin Kang" and r[0]["email"] == "moonjinkang@kaist.ac.kr"
    assert (r[1]["name_ko"], r[1]["name_en"], r[1]["position_raw"]) == ("박진형", "Jinhyung Park", "부교수")  # no link


def test_kaist_cs_first_section_only():
    html = """<p class="line"><span>교수</span></p><ul class="item_box"><li class="horiz_item">
    <div class="item fix" onclick="facultyView(614, 160)"><p class="name">강민석</p><p class="depart">부교수</p>
    <p class="part">Network security</p></div></li></ul>
    <p class="line"><span>명예교수</span></p><ul class="item_box"><li class="horiz_item">
    <div class="item fix" onclick="facultyView(1, 160)"><p class="name">홍길동</p></div></li></ul>"""
    r = kaist_depts.parse_cs_list(html)
    assert [x["name_ko"] for x in r] == ["강민석"] and "idx=614" in r[0]["url"]


def test_snu_cms_and_cse():
    ko = """<a href="/research-faculty/faculty/fulltime?mode=view&profidx=45">강동민 <em>부교수</em></a>
    <a href="/research-faculty/faculty/fulltime?mode=view&profidx=45"><img/></a>"""
    r = snu_depts.parse_cms_list(ko, "https://physics.snu.ac.kr/")
    assert r == {"45": {"name": "강동민", "position_raw": "부교수",
                        "url": "https://physics.snu.ac.kr/research-faculty/faculty/fulltime?mode=view&profidx=45"}}
    cse = """<article><a aria-label="곽노준 교수 상세 페이지로 이동" href="/ko/people/faculty/209"></a>
    <div class="flex flex-col items-start break-keep">곽노준 교수, 지능정보융합학과 겸무 (02) 880-9593 nojunk@snu.ac.kr</div></article>
    <article><a aria-label="강유 교수 상세 페이지로 이동" href="/ko/people/faculty/1"></a>
    <div class="flex flex-col items-start break-keep">강유 교수, 협동과정 인공지능 전공주임 데이터 마이닝 연구실 (02) 880-7254 ukang@snu.ac.kr</div></article>"""
    r = snu_depts.parse_cse_list(cse, "https://cse.snu.ac.kr/")
    assert r["209"]["adjunct"] and not r["1"]["adjunct"] and r["1"]["email"] == "ukang@snu.ac.kr"
    assert "880" not in r["1"]["note"]


def test_snu_math():
    html = """<div class="item"><div class="item-caption"><h4>강명주(Myung-ju Kang) <span class="tack-icon">교수</span></h4>
    <ul><li>Email :<a href="mailto:mkang@snu.ac.kr"></a></li><li><span class="tack-icon">Numerical Analysis</span></li></ul></div></div>"""
    r = snu_depts.parse_math_list(html, "https://www.math.snu.ac.kr/")
    assert r[0]["name_ko"] == "강명주" and r[0]["name_en"] == "Myung-ju Kang" and r[0]["fields"] == ["Numerical Analysis"]


def test_gist_bilingual_and_phys():
    assert gist.split_bilingual("김민곤 Kim, Min-Gon") == ("김민곤", "Min-Gon Kim")
    assert gist.split_bilingual("권용훈") == ("권용훈", None)
    html = """<section class="faculty-staff-wrap">조병익 Cho, Byoung-Ick Lab. 고에너지밀도물리 연구실 Position. Professor(Chair of Department)
    Email bicho@gist.ac.kr Tel 062</section><section class="faculty-staff-wrap">이강은 Lee, Gang Eun Position. Student Affair
    Email x@gist.ac.kr</section>"""
    r = gist_depts.parse_phys_list(html)
    assert r[0]["name_en"] == "Byoung-Ick Cho" and r[0]["lab_name"] == "고에너지밀도물리 연구실"
    assert r[1]["position_raw"] == "Student Affair"


def test_dgist_tracks():
    cms = """<div class="col"><strong class="title">Hong, Seonki, Ph.D.</strong><span class="position">Associate Professor</span>
    <a class="link home" href="http://bbel.dgist.ac.kr"><span class="link-text">Bioinspired Organic Materials Lab.</span></a>
    <a href="mailto:seonkihong@dgist.ac.kr"></a></div>"""
    r = dgist_tracks.parse_cms_track(cms, "https://www.dgist.ac.kr/")
    assert r[0]["name_en"] == "Seonki Hong" and r[0]["lab_name"] == "Bioinspired Organic Materials Lab."
    site = """<p>Member Faculty Cho, Chang-Hee (조창희) Professor ➕ Semiconductor Quantum Photonics Lab 📝chcho-at-dgist.ac.kr
    Devecioglu , Deniz Olgu Adjunct Professor ➕ ORCiD 📝 deniz -at-dgist.ac.kr Staff Kim , Taehoon ( 김태훈 ) Technical Staff</p>"""
    r = dgist_tracks.parse_site_track(site)
    assert [(x["name_en"], x["name_ko"], x["position_raw"]) for x in r] == [
        ("Chang-Hee Cho", "조창희", "Professor"), ("Deniz Olgu Devecioglu", None, "Adjunct Professor")]
    assert r[1]["lab_name"] is None and r[0]["email"] == "chcho@dgist.ac.kr"


# ------------------------------------------------------------------ roster matching
def author(aid, name, alts=(), domain="Physical Sciences", years=(2025,), field="Physics and Astronomy"):
    return {"id": f"https://openalex.org/{aid}", "display_name": name, "display_name_alternatives": list(alts),
            "orcid": None, "works_count": 50,
            "affiliations": [{"institution": {"id": f"https://openalex.org/{INST}"}, "years": list(years)},
                             {"institution": {"id": "https://openalex.org/I999"}, "years": [2010]}],
            "last_known_institutions": [{"id": f"https://openalex.org/{INST}"}],
            "topics": [{"count": 9, "domain": {"display_name": domain}, "field": {"display_name": field}},
                       {"count": 1, "domain": {"display_name": "Life Sciences"}, "field": {"display_name": "y"}}]}


def test_compact_keeps_only_home_affiliation():
    c = compact(author("A1", "Jin Woo Kim"), INST)
    assert len(c["affiliations"]) == 1 and c["topics"][0]["domain"]["display_name"] == "Physical Sciences"


def test_roster_candidates():
    r = Roster([compact(author("A1", "Jin-Woo Kim"), INST), compact(author("A2", "Jinwoo Park"), INST),
                compact(author("A3", "Kim Seung-Woo"), INST)])
    assert [a["display_name"] for a in r.candidates("Jin Woo Kim", None)] == ["Jin-Woo Kim"]
    assert [a["display_name"] for a in r.candidates(None, "김승우")] == ["Kim Seung-Woo"]
    assert r.candidates(None, "박민수") == []


def fac(dept, **kw):
    base = dict(univ="kaist", dept=dept, is_full_time=True, faculty_list_url="u", faculty_page_url="u",
                retrieved_at=date(2026, 10, 12))
    base.update(kw)
    return FacultyRecord(**base)


def test_field_share_and_topic_check_follow_department():
    a = author("A1", "Jin Woo Kim", domain="Physical Sciences")
    assert field_share(a, ("Physical Sciences",)) == 0.9
    assert evaluate(fac("kaist-phys", name_en="Jin Woo Kim"), a, INST, {}).topic_ok
    assert not evaluate(fac("kaist-life", name_en="Jin Woo Kim"), a, INST, {}).topic_ok


def test_korean_only_name_roster_mode():
    a = author("A1", "Seung-Woo Kim", field="Computer Science")
    # roster department (KAIST CS): full romanisation match is enough; search department needs anchors
    assert evaluate(fac("kaist-cs", name_ko="김승우"), a, INST, {}).strong
    assert not evaluate(fac("kaist-life", name_ko="김승우"), a, INST, {}).strong


# ------------------------------------------------------------------ field rules, joint appointments
def test_alphabetical():
    au = lambda *names: [{"author": {"display_name": n}} for n in names]  # noqa: E731
    assert alphabetical(au("A. Choi", "B. Kim", "C. Park"))
    assert not alphabetical(au("C. Park", "B. Kim", "A. Choi"))
    assert not alphabetical(au("A. Choi", "B. Kim"))  # two authors: too likely by chance


def test_discipline_rules():
    d = config.DISCIPLINES
    assert d["life"].min_papers == config.MIN_SENIOR_PAPERS and not d["life"].max_authors
    assert d["math"].position_agnostic and d["cs"].alphabetical_counts and d["phys"].max_authors == 100


def match(dept, univ, aid, name_ko, name_en=None):
    return MatchResult(univ=univ, dept=dept, name_ko=name_ko, name_en=name_en, faculty_page_url=f"u/{dept}",
                       status="matched",
                       openalex_id=aid, confidence="medium", retrieved_at=date(2026, 10, 12))


def test_group_labs_merges_joint_appointments():
    groups, conflicts = group_labs([match("kaist-chem", "kaist", "A1", "이해신", "Haeshin Lee"),
                                    match("kaist-life", "kaist", "A1", "이해신", "Hae-Shin Lee"),
                                    match("kaist-phys", "kaist", "A2", "김철수", "Chulsoo Kim"),
                                    match("kaist-math", "kaist", "A2", "박영희", "Younghee Park"),  # namesake profile
                                    match("snu-chem", "snu", "A3", "최민수", "Minsu Choi"),
                                    match("postech-chem", "postech", "A3", "최민수", "Minsu Choi")])  # two universities
    assert [[m.dept for m in g] for g in groups] == [["kaist-life", "kaist-chem"]]  # departments.yaml order
    assert {m.openalex_id for m in conflicts} == {"A2", "A3"}


def test_same_korean_name_is_not_a_joint_appointment():
    # KAIST 화학과 김현우 (English name on the page) and 전산학부 김현우 (Korean name only) are two people:
    # the English-name match keeps the profile, the Korean-only match is excluded
    groups, conflicts = group_labs([match("kaist-chem", "kaist", "A1", "김현우", "Hyunwoo Kim"),
                                    match("kaist-cs", "kaist", "A1", "김현우", None)])
    assert [[m.dept for m in g] for g in groups] == [["kaist-chem"]]
    assert [m.dept for m in conflicts] == ["kaist-cs"]


def test_topic_check_uses_fields():
    chemist = author("A1", "Hyunwoo Kim")
    chemist["topics"] = [{"count": 10, "domain": {"display_name": "Physical Sciences"}, "field": {"display_name": "Chemistry"}}]
    assert evaluate(fac("kaist-chem", name_en="Hyunwoo Kim"), chemist, INST, {}).topic_ok
    assert not evaluate(fac("kaist-cs", name_ko="김현우"), chemist, INST, {}).topic_ok


class FakeOA:
    """works_for_author stub: author id -> list of (position, corresponding) in the window."""
    def __init__(self, roles):
        self.roles = roles

    def works_for_author(self, aid, from_year):
        for i, (pos, corr) in enumerate(self.roles.get(aid, [])):
            yield ({"type": "article", "publication_year": 2024, "authorships": [
                {"author": {"id": f"https://openalex.org/{aid}"}, "author_position": pos, "is_corresponding": corr},
                {"author": {"id": "https://openalex.org/X"}, "author_position": "first"}]}, date(2026, 10, 12))


def test_roster_tiebreak_picks_the_candidate_leading_papers():
    from pipeline.step03_match import roster_tiebreak
    f = fac("kaist-phys", name_en="Sungjae Cho")
    a = evaluate(f, author("A1", "Sungjae Cho"), INST, {})
    b = evaluate(f, author("A2", "Sung Jae Cho"), INST, {})
    pi = [("last", True)] * 12
    student = [("first", False)] * 9 + [("last", False)] * 2
    chosen, why = roster_tiebreak(FakeOA({"A1": pi, "A2": student}), f, [a, b])
    assert chosen.openalex_id == "A1" and "12 vs 2" in why
    # two candidates both leading papers: stay ambiguous
    chosen, _ = roster_tiebreak(FakeOA({"A1": pi, "A2": pi[:6]}), f, [a, b])
    assert chosen is None


def test_roster_tiebreak_same_orcid():
    from pipeline.step03_match import roster_tiebreak
    f = fac("kaist-phys", name_en="Eun-Gook Moon")
    a = evaluate(f, {**author("A1", "Eun-Gook Moon"), "orcid": "https://orcid.org/0000-0003-1863-4901", "works_count": 67}, INST, {})
    b = evaluate(f, {**author("A2", "Eun-Gook Moon"), "orcid": "https://orcid.org/0000-0003-1863-4901", "works_count": 15}, INST, {})
    chosen, _ = roster_tiebreak(FakeOA({}), f, [a, b])
    assert chosen.openalex_id == "A1"


# ------------------------------------------------------------------ manual match review (PLAN_PHASE2.md 5-2)
def _matched(name_ko="김철수"):
    return MatchResult(univ="kaist", dept="kaist-math", name_ko=name_ko, faculty_page_url="u", status="matched",
                       openalex_id="A1", confidence="medium", detail="single strong candidate",
                       retrieved_at=date(2026, 11, 3))


class _FakeOA:
    def author(self, aid):
        return {"display_name": "Real Person", "works_count": 40, "orcid": "https://orcid.org/0000-1"}, date(2026, 11, 3)


def test_override_force_records_new_candidate():
    used = set()
    ov = {"force": {"kaist-math|김철수": {"openalex_id": "A2", "note": "namesake"}}, "exclude": {}}
    r = apply_override(_FakeOA(), _matched(), ov, used)
    assert (r.status, r.openalex_id, r.detail) == ("matched", "A2", "manual review: namesake")
    assert r.candidates[0].openalex_id == "A2" and used == {"kaist-math|김철수"}


def test_override_exclude_clears_the_match():
    ov = {"force": {}, "exclude": {"kaist-math|김철수": {"note": "no profile"}}}
    r = apply_override(_FakeOA(), _matched(), ov, set())
    assert (r.status, r.openalex_id, r.confidence, r.reason) == ("excluded", None, None, "manual_review")


def test_override_leaves_others_alone():
    r = _matched("이영희")
    assert apply_override(_FakeOA(), r, {"force": {}, "exclude": {}}, set()) is r


# ------------------------------------------------------------------ similarity display (PLAN_PHASE2.md 5-3)
def test_closest_paper_pairs_uses_each_paper_once_and_skips_shared():
    a = np.array([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]])
    b = np.array([[1.0, 0.0], [0.0, 1.0]])
    t = {p: f"distinct paper title {p}" for p in ["p1", "p2", "p3", "q1", "q2"]}
    assert closest_paper_pairs(["p1", "p2", "p3"], a, ["q1", "q2"], b, t) == [("p1", "q1"), ("p3", "q2")]
    # the same paper on both sides is dropped everywhere, not just where it would pair with itself
    assert closest_paper_pairs(["p1", "p3"], a[[0, 2]], ["p1", "q2"], b, t) == [("p3", "q2")]
    # also when it has two ids (a preprint and the journal version)
    t["q1"] = t["p1"]
    assert closest_paper_pairs(["p1", "p3"], a[[0, 2]], ["q1", "q2"], b, t) == [("p3", "q2")]


def test_similarity_band_boundaries():
    cuts = band_cuts([0.92, 0.93, 0.94, 0.95, 0.96, 0.97])
    assert cuts[0] < cuts[1]
    assert similarity_band(0.99, cuts, 0.9) == "매우 가까움"
    assert similarity_band(cuts[1], cuts, 0.9) == "매우 가까움"
    assert similarity_band(cuts[0], cuts, 0.9) == "가까움"
    assert similarity_band(0.91, cuts, 0.9) == "비교적 가까움"
    assert similarity_band(0.89, cuts, 0.9) == "주제 거리가 있음"


def test_self_retrieval_rank_finds_the_matching_half():
    others = np.array([[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]])
    half_a, half_b = np.array([0.0, 1.0]), np.array([0.0, 1.0])
    assert self_retrieval_rank(half_a, half_b, others, 1) == 1
    assert self_retrieval_rank(np.array([1.0, 0.0]), half_b, others, 1) == 3


def test_split_cluster_finds_two_groups_and_keeps_small_clusters_whole():
    rng = np.random.RandomState(0)
    base = np.eye(8)[[0] * 12 + [1] * 12]           # two groups of 12 labs pointing in different directions
    vec = base + 0.05 * rng.randn(24, 8)
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)
    parts = split_cluster(vec @ vec.T)
    assert sorted(len(p) for p in parts) == [12, 12]
    assert all(p <= set(range(12)) or p <= set(range(12, 24)) for p in parts)
    small = vec[:10] @ vec[:10].T
    assert split_cluster(small) == [set(range(10))]


# ------------------------------------------------------------------ research direction (PLAN_PHASE2.md 5-6)
def test_shift_test_separates_a_real_change_from_sampling_noise():
    rng = np.random.RandomState(1)
    a, b = np.eye(6)[0], np.eye(6)[1]
    same = a + 0.3 * rng.randn(16, 6)
    moved = np.vstack([a + 0.3 * rng.randn(8, 6), b + 0.3 * rng.randn(8, 6)])
    _, p_same = shift_test(same[:8], same[8:], rng, permutations=200)
    shift, p_moved = shift_test(moved[:8], moved[8:], rng, permutations=200)
    assert p_moved < 0.01 < p_same and shift > 0


def test_benjamini_hochberg_and_topic_shift():
    assert benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}, q=0.05) == {"a", "b"}
    t = lambda *names: {"topics": [{"name": n, "score": 1.0} for n in names]}  # noqa: E731
    grew, shrank = topic_shift([t("A"), t("A"), t("B")], [t("C"), t("C"), t("B")])
    assert grew == ["C"] and shrank == ["A"]


def test_drop_outliers_sets_aside_a_namesake_paper():
    rng = np.random.RandomState(2)
    core = np.eye(6)[0]
    own = core + 0.1 * rng.randn(9, 6)
    stranger = np.eye(6)[3][None, :]
    vecs = np.vstack([own, stranger])
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    kept, kv = drop_outliers([{"id": i} for i in range(10)], vecs, core)
    assert [p["id"] for p in kept] == list(range(9)) and len(kv) == 9


def test_map_place_follows_the_most_similar_labs():
    V = np.eye(4)
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [5.0, 5.0]])
    assert map_place(np.array([0, 1.0, 0, 0]), V, xy, skip=0, k=2) == [1.0, 0.0]
