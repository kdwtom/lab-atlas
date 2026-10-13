"""Data schemas (pydantic v2).

Two groups:
- Intermediate pipeline records (FacultyRecord, MatchResult, RawPaper, LabStatus) — internal only.
- Web data (Lab, Paper, Edge, Cluster, Meta) — mirrored 1:1 by web/src/types/data.ts.

Unknown values are None (rendered as "정보 없음"). Every record carries source URLs and dates.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Univ = Literal["kaist", "snu", "postech", "unist", "gist", "dgist"]
SourceKind = Literal[
    "faculty_page", "faculty_detail", "openalex_author", "openalex_works",
    "semantic_scholar", "homepage",
]
AuthorPosition = Literal["first", "middle", "last"]
Discipline = Literal["life", "chem", "phys", "math", "cs"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    url: str
    kind: SourceKind
    retrieved_at: date


# =================================================================== intermediate
class FacultyRecord(Strict):
    """One professor as listed on the official faculty page."""
    univ: Univ
    dept: str                                 # department code (departments.yaml)
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    position_raw: Optional[str] = None
    position: Optional[str] = None           # normalised: 교수/부교수/조교수 or None
    is_full_time: bool                        # listed under a full-time faculty roster/category
    lab_name: Optional[str] = None
    homepage_url: Optional[str] = None
    email: Optional[str] = None               # internal only, used for de-duplication/joins
    orcid: Optional[str] = None
    research_fields: list[str] = Field(default_factory=list)
    anchor_citations: list[str] = Field(default_factory=list)  # publication strings on the page
    faculty_list_url: str
    faculty_page_url: str                     # detail page if any, else the list page
    retrieved_at: date


class CandidateEvidence(Strict):
    openalex_id: str
    display_name: str
    orcid: Optional[str] = None
    works_count: int = 0
    affiliation_ok: bool = False
    affiliation_years: list[int] = Field(default_factory=list)
    name_ok: bool = False
    name_note: Optional[str] = None
    field_share: float = 0.0                  # share of top topics in the department field's domains
    topic_ok: bool = False
    anchor_hits: int = 0
    orcid_match: Optional[bool] = None
    strong: bool = False
    pi_papers: Optional[int] = None           # roster tie-break: papers counting toward the field's rule


MatchStatus = Literal["matched", "excluded"]
ExcludeReason = Literal[
    "not_full_time", "no_candidate", "affiliation_mismatch", "name_mismatch",
    "topic_mismatch", "ambiguous_multiple_candidates", "no_english_name_no_anchor",
    "below_paper_threshold",
]


class MatchResult(Strict):
    univ: Univ
    dept: str
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    faculty_page_url: str
    status: MatchStatus
    openalex_id: Optional[str] = None
    confidence: Optional[Literal["high", "medium"]] = None
    reason: Optional[ExcludeReason] = None
    detail: Optional[str] = None
    candidates: list[CandidateEvidence] = Field(default_factory=list)
    institution_id: Optional[str] = None
    retrieved_at: date


class PiRole(Strict):
    position: AuthorPosition
    is_corresponding: bool
    # PI's authorship lists the matched institution (or no institution at all). Papers where it lists
    # only other institutions still count toward the selection criterion, but are left out of the
    # analysis (similarity, keywords, representative papers) because merged OpenAlex profiles can
    # contain namesakes' papers.
    at_home_institution: bool = True
    # counted toward the selection criterion although not last/corresponding author: fields where author
    # order is alphabetical (mathematics: every paper; computing: papers with >= 3 authors in that order)
    order_agnostic: bool = False


class Topic(Strict):
    id: str
    name: str
    score: float
    subfield: Optional[str] = None
    field: Optional[str] = None
    domain: Optional[str] = None


class RawPaper(Strict):
    """Internal record incl. abstract — never published on the site."""
    id: str
    lab_ids: list[str]
    title: str
    year: int
    publication_date: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    cited_by_count: int
    type: str
    pi_roles: dict[str, PiRole]
    abstract: Optional[str] = None
    tldr: Optional[str] = None
    topics: list[Topic] = Field(default_factory=list)
    coauthor_ids: list[str] = Field(default_factory=list)
    openalex_url: str
    retrieved_at: date


class LabStatus(Strict):
    lab_id: str
    univ: Univ
    depts: list[str]                       # department codes (a professor listed by two departments is one lab)
    discipline: Discipline                 # field whose selection rule applied (first department)
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    openalex_id: str
    paper_count_5y: int
    senior_paper_count_5y: int
    meets_criterion: bool
    abstract_count: int
    senior_abstract_count: int
    home_paper_count_5y: int = 0           # papers with at_home_institution (analysis set)
    home_senior_abstract_count: int = 0    # representative-paper candidates


# =================================================================== web data
class PaperSummary(Strict):
    one_line: str
    background: str
    methods: str
    findings: str
    significance: str


class YearKeywords(Strict):
    year: int
    keywords: list[str]


class Lab(Strict):
    id: str
    univ: Univ
    univ_name_ko: str
    dept_name_ko: str                      # all departments, joined with " · "
    dept_codes: list[str]
    disciplines: list[Discipline]
    pi_name_ko: Optional[str] = None
    pi_name_en: Optional[str] = None
    position: Optional[str] = None
    lab_name: Optional[str] = None
    homepage_url: Optional[str] = None
    faculty_page_url: str
    openalex_id: str
    orcid: Optional[str] = None
    match_confidence: Literal["high", "medium"]
    paper_count_5y: int
    senior_paper_count_5y: int
    keywords: list[str] = Field(default_factory=list)
    cluster_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    intro_ko: Optional[str] = None
    representative_paper_ids: list[str] = Field(default_factory=list, max_length=3)
    keyword_timeline: list[YearKeywords] = Field(default_factory=list)
    sources: list[Source]


class Paper(Strict):
    id: str
    lab_ids: list[str]
    title: str
    year: int
    venue: Optional[str] = None
    doi: Optional[str] = None
    cited_by_count: int
    type: str
    pi_roles: dict[str, PiRole]
    has_abstract: bool
    has_tldr: bool
    topics: list[Topic] = Field(default_factory=list)
    summary_ko: Optional[PaperSummary] = None
    openalex_url: str
    retrieved_at: date


class Edge(Strict):
    source: str
    target: str
    type: Literal["similarity", "coauthor"]
    weight: float
    cross: bool = False                    # the two labs belong to different fields (disciplines)
    reasons: list[str] = Field(default_factory=list, max_length=3)
    paper_ids: list[str] = Field(default_factory=list)


class Cluster(Strict):
    id: int
    label_ko: str
    keywords: list[str]
    size: int


class Counts(Strict):
    labs: int
    papers: int
    edges_similarity: int
    edges_coauthor: int


class SummaryCoverage(Strict):
    """How much hand-written Korean content exists (the site shows "정보 없음" for the rest)."""
    representative_papers: int
    papers_with_summary: int
    labs: int
    labs_with_intro: int


class DepartmentInfo(Strict):
    code: str
    univ: Univ
    univ_name_ko: str
    name_ko: str
    discipline: Discipline
    faculty_list_url: str
    labs: int                              # labs listing this department (joint appointments count in each)


class Meta(Strict):
    generated_at: date
    data_retrieved_at: date
    window_years: tuple[int, int]
    min_senior_papers: int
    louvain_resolution: Optional[float] = None
    louvain_seed: Optional[int] = None
    similarity_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    counts: Counts
    summary_coverage: Optional[SummaryCoverage] = None
    excluded_namesake_papers: int = 0
    departments: list[DepartmentInfo] = Field(default_factory=list)
    rules: dict[str, str] = Field(default_factory=dict)  # field code -> selection rule (Korean)
