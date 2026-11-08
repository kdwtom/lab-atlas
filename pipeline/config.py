"""Pipeline configuration: scope, selection criteria, rate limits, paths."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "pipeline"
CACHE_DIR = PIPELINE_DIR / "cache"
OUTPUT_DIR = PIPELINE_DIR / "output"
WEB_DATA_DIR = ROOT / "web" / "public" / "data"

try:  # optional .env support
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "local.env")  # alternative name (also git-ignored)
except ImportError:  # pragma: no cover
    pass

# ---------------------------------------------------------------- time window
TODAY = date.today()
WINDOW_YEARS = 5
YEAR_TO = TODAY.year
YEAR_FROM = YEAR_TO - WINDOW_YEARS + 1  # inclusive, e.g. 2022..2026

# ---------------------------------------------------------------- criteria
MIN_SENIOR_PAPERS = 5                      # last-author or corresponding papers in window
COUNTED_WORK_TYPES = {"article", "review"}  # OpenAlex work types counted toward the criterion
FULL_TIME_POSITIONS = {"교수", "부교수", "조교수"}  # normalised positions treated as full-time

# ---------------------------------------------------------------- matching
CURRENT_AFFILIATION_YEARS = 3       # affiliation with institution must appear within this many recent years
SPLIT_PROFILE_RATIO = 0.10          # smaller duplicate profile has <= 10% of works of the larger
MAX_ANCHOR_PAPERS = 8               # faculty-page publications used as anchors per PI
ANCHOR_TITLE_SIMILARITY = 90        # rapidfuzz partial_ratio threshold (0-100)

# ---------------------------------------------------------------- analysis (stage 3)
EMBED_MODEL = "sentence-transformers/allenai-specter"
EMBED_MAX_PAPERS = 30               # most recent analysis papers per lab (senior-author papers first)
SIMILARITY_K = 5                    # top-k neighbours per lab
SIMILARITY_THRESHOLD_QUANTILE = 0.25  # threshold = this quantile of all labs' top-k similarities
LOUVAIN_SEED = 42
LOUVAIN_TARGET_CLUSTERS = (6, 12)
LOUVAIN_RESOLUTIONS = [round(0.5 + 0.05 * i, 2) for i in range(51)]  # 0.5 .. 3.0
# sub-clusters: a cluster this large is split again on its own kNN graph (shown when the map is zoomed in)
SUBCLUSTER_MIN_SIZE = 20
SUBCLUSTER_MIN_PART = 4                 # no sub-cluster smaller than this
SUBCLUSTER_LABS_PER_PART = 10           # aim for about one sub-cluster per this many labs
SUBCLUSTER_RESOLUTIONS = [round(0.5 + 0.1 * i, 1) for i in range(26)]  # 0.5 .. 3.0
UMAP_SEED = 42
FLAG_COSINE = 0.70                  # papers further than this from their lab centre go to manual review
REPRESENTATIVE_PAPERS = 3
RECENT_PAPER_YEARS = 2              # at least one representative paper from the last 2 years

# ---------------------------------------------------------------- APIs
OPENALEX_BASE = "https://api.openalex.org"
OPENALEX_MAILTO = os.environ.get("OPENALEX_MAILTO", "").strip()
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()  # optional
OPENALEX_MIN_INTERVAL = 0.2         # seconds between requests (<= 5 req/s; limit is 10)
S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY", "").strip()
S2_MIN_INTERVAL = 1.1 if not S2_API_KEY else 0.35
WEB_MIN_INTERVAL = 1.0              # politeness delay for university websites
HTTP_TIMEOUT = 30
USER_AGENT = "LabAtlas/0.1 (portfolio research project; +https://github.com/)"


@dataclass(frozen=True)
class Discipline:
    code: str
    name_ko: str
    topic_domains: tuple[str, ...]   # OpenAlex domains accepted as "in field" when checking a candidate
    min_papers: int                  # selection threshold over the window
    position_agnostic: bool = False  # count every authorship (fields with alphabetical author order)
    alphabetical_counts: bool = False  # also count papers whose >= 3 authors are in alphabetical order
    max_authors: int | None = None   # papers with more authors are ignored for this field (large collaborations)
    # OpenAlex fields accepted as "in field" (finer than domains: Physical Sciences holds chemistry, physics and
    # computing alike, so a domain check cannot tell a chemist from a computer scientist). None = use domains.
    topic_fields: tuple[str, ...] | None = None
    extra_work_types: tuple[str, ...] = ()  # counted besides COUNTED_WORK_TYPES (computing: conference papers)

    @property
    def work_types(self) -> set[str]:
        return COUNTED_WORK_TYPES | set(self.extra_work_types)


DISCIPLINES: dict[str, Discipline] = {d.code: d for d in [
    Discipline("life", "생명과학", ("Life Sciences",), MIN_SENIOR_PAPERS),
    Discipline("chem", "화학", ("Physical Sciences", "Life Sciences"), MIN_SENIOR_PAPERS, topic_fields=(
        "Chemistry", "Materials Science", "Chemical Engineering", "Biochemistry, Genetics and Molecular Biology",
        "Physics and Astronomy", "Energy", "Environmental Science", "Pharmacology, Toxicology and Pharmaceutics",
        "Engineering")),
    Discipline("phys", "물리", ("Physical Sciences",), MIN_SENIOR_PAPERS, max_authors=100, topic_fields=(
        "Physics and Astronomy", "Materials Science", "Engineering", "Earth and Planetary Sciences", "Energy",
        "Mathematics", "Computer Science", "Chemistry")),
    Discipline("math", "수학", ("Physical Sciences", "Social Sciences"), 4, position_agnostic=True, topic_fields=(
        "Mathematics", "Computer Science", "Decision Sciences", "Physics and Astronomy",
        "Economics, Econometrics and Finance", "Engineering")),
    Discipline("cs", "컴퓨터", ("Physical Sciences", "Social Sciences"), MIN_SENIOR_PAPERS,
               alphabetical_counts=True, max_authors=100, extra_work_types=("conference-paper",), topic_fields=(
        "Computer Science", "Mathematics", "Engineering", "Decision Sciences", "Social Sciences", "Psychology",
        "Neuroscience")),
]}
TOPIC_SHARE = 0.40                  # share of an author's top topics that must fall in the field's domains


@dataclass(frozen=True)
class Department:
    code: str              # unique, e.g. "kaist-chem"
    univ: str              # short university code used in lab ids
    univ_name_ko: str
    univ_name_en: str
    dept_name_ko: str
    discipline: str        # key of DISCIPLINES
    faculty_list_url: str  # the page we cite as the faculty roster
    institution_query: str  # OpenAlex institution search string
    parser: str            # key of lib.faculty.PARSERS
    options: dict = field(default_factory=dict, hash=False, compare=False)  # parser options
    matching: str = "search"  # "search": name search per professor; "roster": institution author roster
    max_anchor_papers: int = MAX_ANCHOR_PAPERS

    @property
    def disc(self) -> Discipline:
        return DISCIPLINES[self.discipline]


def load_departments(path: Path = PIPELINE_DIR / "departments.yaml") -> list[Department]:
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    univs = raw["universities"]
    out = []
    for d in raw["departments"]:
        u = univs[d["univ"]]
        out.append(Department(
            code=d["code"], univ=d["univ"], univ_name_ko=u["name_ko"], univ_name_en=u["name_en"],
            dept_name_ko=d["name_ko"], discipline=d["discipline"], faculty_list_url=d["url"],
            institution_query=u["openalex_query"], parser=d["parser"], options=d.get("options") or {},
            matching=d.get("matching", "search"),
            max_anchor_papers=d.get("max_anchor_papers", MAX_ANCHOR_PAPERS),
        ))
    codes = [d.code for d in out]
    dup = {c for c in codes if codes.count(c) > 1}
    if dup or any(d.discipline not in DISCIPLINES for d in out):
        raise SystemExit(f"departments.yaml: duplicate codes {dup} or unknown discipline")
    return out


DEPARTMENTS: list[Department] = load_departments()
DEPT_BY_CODE = {d.code: d for d in DEPARTMENTS}
UNIVERSITIES: dict[str, Department] = {}  # first department per university (names, OpenAlex query)
for _d in DEPARTMENTS:
    UNIVERSITIES.setdefault(_d.univ, _d)


def require_mailto() -> str:
    if not OPENALEX_MAILTO or "@" not in OPENALEX_MAILTO:
        raise SystemExit(
            "OPENALEX_MAILTO가 설정되지 않았습니다. 프로젝트 루트의 .env 파일에 "
            "OPENALEX_MAILTO=you@example.com 을 넣거나 환경변수로 지정하세요."
        )
    return OPENALEX_MAILTO
