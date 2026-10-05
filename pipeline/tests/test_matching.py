from datetime import date

from pipeline.lib.names import names_compatible, normalize_position, search_variants, surname_compatible
from pipeline.lib.textutil import reconstruct_abstract, title_from_citation
from pipeline.schemas import FacultyRecord
from pipeline.step03_match import decide, evaluate

INST = "I111"


def fac(**kw):
    base = dict(univ="kaist", is_full_time=True, faculty_list_url="u", faculty_page_url="u",
                retrieved_at=date(2026, 10, 4))
    base.update(kw)
    return FacultyRecord(**base)


def author(aid, name, years=(2025,), life=8, other=2, works=100, orcid=None, inst=INST):
    return {
        "id": f"https://openalex.org/{aid}", "display_name": name, "display_name_alternatives": [],
        "orcid": f"https://orcid.org/{orcid}" if orcid else None, "works_count": works,
        "affiliations": [{"institution": {"id": f"https://openalex.org/{inst}"}, "years": list(years)}],
        "topics": [{"count": life, "domain": {"display_name": "Life Sciences"}},
                   {"count": other, "domain": {"display_name": "Physical Sciences"}}],
    }


def test_names():
    assert names_compatible("Jin Woo Kim", "Jin-Woo Kim")
    assert names_compatible("Kim, Jinwoo", "Jinwoo Kim")
    assert names_compatible("Alexander Bae", "J. Alexander Bae")
    assert names_compatible("June M. Kwak", "June Myoung Kwak")
    assert not names_compatible("Jin Woo Kim", "Sang Woo Kim")
    assert not names_compatible("Mi Young Kim", "Mi Kim")
    assert names_compatible("Seung-Jae V. Lee", "Seung-Jae Lee")
    assert names_compatible("Young-Joon Kim", "Youngjoon Kim")
    assert not names_compatible("Jin Woo Kim", "Jin Ho Kim")
    assert surname_compatible("박지환", "Jihwan Park") is True
    assert surname_compatible("박지환", "Jihwan Lee") is False
    assert surname_compatible("라젠드라 카르키", "Rajendra Karki") is None
    assert "Young-Joon KIM" in search_variants("KIM Young-Joon")


def test_positions():
    assert normalize_position("Assistant Professor") == "조교수"
    assert normalize_position("Professor. Head of Department") == "교수"
    assert normalize_position("명예교수") is None
    assert normalize_position("연구교수") is None
    assert normalize_position("부교수") == "부교수"


def test_given_name_romanisation():
    from pipeline.lib.names import given_name_compatible as g
    for ko, en in [("이승우", "Seungwoo Lee"), ("이승우", "Sung Woo Lee"), ("임신혁", "Sin-Hyeog Im"),
                   ("정민환", "Min Whan Jung"), ("허원도", "Won Do Heo"), ("김은준", "Eunjoon Kim"),
                   ("이지오", "Jie-Oh Lee")]:
        assert g(ko, en) is True, (ko, en)
    assert g("이승우", "Hyomin Lee") is False  # co-author sharing only the surname
    assert g("김윤기", "S. Kim") is None


def test_citations_and_abstract():
    assert title_from_citation(
        "Kim J*, Kang C# (2025) Autophagy-dependent splicing control directs translation toward "
        "inflammation during senescence. Developmental Cell 60(3), 364-378"
    ) == "Autophagy-dependent splicing control directs translation toward inflammation during senescence"
    assert title_from_citation(
        "A hierarchy of intestinal antigens instructs the CD4 T cell receptor repertoire, Immunity, , 58, 1217-1235 (2025 )"
    ) == "A hierarchy of intestinal antigens instructs the CD4 T cell receptor repertoire"
    assert title_from_citation("Non-canonical activation of ERK at endosomes, 2022, Nature") == \
        "Non-canonical activation of ERK at endosomes"
    assert title_from_citation(
        'van Kempen, M., Kim, S., Söding, J.*, and Steinegger, M.* (2023) "Fast and accurate protein '
        'structure search with Foldseek", Nature Biotechnology, doi: 10.1101/2022.02.07.479398'
    ) == "Fast and accurate protein structure search with Foldseek"
    assert title_from_citation(
        "Continued clearance of apoptotic cells critically depends on the phagocyte Ucp2 protein. / "
        "Park D, Han CZ, Ravichandran KS. Nature 2011"
    ) == "Continued clearance of apoptotic cells critically depends on the phagocyte Ucp2 protein"
    assert title_from_citation(
        "Y. J. Park, S. Lee, S. Kim, and J. B. Kim*. Dnmt1 maintains metabolic fitness of adipocytes "
        "through acting as an epigenetic safeguard of mitochondria. PNAS 118, e2021073118 (2021)"
    ) == ("Dnmt1 maintains metabolic fitness of adipocytes through acting as an epigenetic "
          "safeguard of mitochondria")
    assert reconstruct_abstract({"world": [1], "hello": [0]}) == "hello world"


def test_single_strong_candidate():
    f = fac(name_en="Jin Woo Kim")
    good = evaluate(f, author("A1", "Jin-Woo Kim"), INST, {})
    old = evaluate(f, author("A2", "Jin Woo Kim", years=(2010,)), INST, {})
    chem = evaluate(f, author("A3", "Jinwoo Kim", life=1, other=9), INST, {})
    assert good.strong and not old.strong and not chem.strong
    chosen, reason, _ = decide(f, [good, old, chem])
    assert chosen.openalex_id == "A1" and reason is None


def test_ambiguous_is_excluded():
    f = fac(name_en="Jin Woo Kim")
    a = evaluate(f, author("A1", "Jin Woo Kim", works=120), INST, {})
    b = evaluate(f, author("A2", "Jin Woo Kim", works=90), INST, {})
    chosen, reason, _ = decide(f, [a, b])
    assert chosen is None and reason == "ambiguous_multiple_candidates"


def test_anchor_breaks_tie_and_split_profile():
    f = fac(name_en="Jin Woo Kim")
    a = evaluate(f, author("A1", "Jin Woo Kim", works=120), INST, {"A2": 2})
    b = evaluate(f, author("A2", "Jin Woo Kim", works=90), INST, {"A2": 2})
    assert decide(f, [a, b])[0].openalex_id == "A2"
    big = evaluate(f, author("A1", "Jin Woo Kim", works=300), INST, {})
    tiny = evaluate(f, author("A9", "Jin Woo Kim", works=12), INST, {})
    assert decide(f, [big, tiny])[0].openalex_id == "A1"


def test_korean_only_name_needs_anchors():
    f = fac(univ="postech", name_ko="김광순", anchor_citations=["x"])
    assert evaluate(f, author("A1", "Kwang Soon Kim"), INST, {"A1": 1}).strong
    assert not evaluate(f, author("A1", "Kwang Soon Kim"), INST, {}).strong
    # co-author sharing only the surname is rejected even with many anchors
    assert not evaluate(f, author("A2", "Hyomin Kim"), INST, {"A2": 3}).strong
    # initials only: surname evidence alone needs two anchors
    assert not evaluate(f, author("A3", "K. Kim"), INST, {"A3": 1}).strong
    assert evaluate(f, author("A3", "K. Kim"), INST, {"A3": 2}).strong


def test_dominant_anchor_author():
    f = fac(univ="snu", name_en="V. Narry Kim", anchor_citations=["x"])
    main = evaluate(f, author("A1", "V. Narry Kim", works=159), INST, {"A1": 7, "A2": 1})
    dup = evaluate(f, author("A2", "V. Narry Kim", works=65), INST, {"A1": 7, "A2": 1})
    assert decide(f, [main, dup])[0].openalex_id == "A1"


def test_alternative_names_need_anchor():
    f = fac(name_en="Sang-Gyu Kim")
    a = author("A1", "Hyojoong Kim")
    a["display_name_alternatives"] = ["Sang-Gyu Kim"]
    assert not evaluate(f, a, INST, {}).name_ok
    assert evaluate(f, a, INST, {"A1": 1}).name_ok


def test_reasons():
    f = fac(name_en="Jin Woo Kim")
    assert decide(f, [])[1] == "no_candidate"
    other_inst = evaluate(f, author("A1", "Jin Woo Kim", inst="I999"), INST, {})
    assert decide(f, [other_inst])[1] == "affiliation_mismatch"
    wrong_name = evaluate(f, author("A1", "Min Su Park"), INST, {})
    assert decide(f, [wrong_name])[1] == "name_mismatch"
