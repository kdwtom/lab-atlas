import pytest

from pipeline.namesake import Features, decide, score


def feat(oid, works=10, home=8, co=0, fs=1.0, anchor=0, name_ok=True):
    return Features(openalex_id=oid, display_name=oid, name_ok=name_ok, affiliation_ok=True, field_share=fs,
                    anchor_hits=anchor, works_window=works, home_recent=home, dept_coauthor=co)


def test_no_papers_scores_negative():
    assert score(feat("A", works=0, home=0)) < 0
    assert score(feat("A", name_ok=False)) < 0


def test_fragment_cannot_take_full_home_share():
    assert score(feat("frag", works=1, home=1)) < score(feat("main", works=20, home=18))


def test_clear_winner_is_certain():
    d = decide([feat("main", works=30, home=28, co=3), feat("doctor", works=40, home=2, fs=0.0)])
    assert d.choice == "main" and d.certain


def test_profile_tied_only_by_name_is_not_certain():
    # one home paper out of six, no colleagues, no anchor: send to the adjudicator
    d = decide([feat("A", works=6, home=1, fs=0.75), feat("B", works=19, home=3, fs=0.0)])
    assert d.choice == "A" and not d.certain


def test_nobody_with_papers_is_not_certain():
    d = decide([feat("A", works=0, home=0)])
    assert d.choice is None and not d.certain


def test_medoid_similarity_isolates_foreign_minority():
    np = pytest.importorskip("numpy")  # CI installs requirements.txt only
    from pipeline.namesake_papers import medoid_similarity
    rng = np.random.RandomState(0)
    core = np.array([1.0, 0, 0, 0]) + 0.05 * rng.randn(8, 4)
    foreign = np.array([0, 0, 1.0, 0]) + 0.05 * rng.randn(3, 4)
    s = medoid_similarity(np.vstack([core, foreign]))
    assert s[:8].min() > s[8:].max()
