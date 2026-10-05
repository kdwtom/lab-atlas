"""Pipeline configuration: scope, selection criteria, rate limits, paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
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
LIFE_SCI_TOPIC_SHARE = 0.40         # share of author's top topics in "Life Sciences" domain
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
class Department:
    univ: str              # short code used in ids
    univ_name_ko: str
    univ_name_en: str
    dept_name_ko: str
    faculty_list_url: str  # the page we cite as the faculty roster
    institution_query: str  # OpenAlex institution search string


DEPARTMENTS: list[Department] = [
    Department(
        "kaist", "KAIST", "Korea Advanced Institute of Science and Technology", "생명과학과",
        "https://bio.kaist.ac.kr/doc/ko/selectDocList.do?menuSeq=3344&bbsSeq=120",
        "Korea Advanced Institute of Science and Technology",
    ),
    Department(
        "snu", "서울대학교", "Seoul National University", "생명과학부",
        "https://biosci.snu.ac.kr/people/faculty",
        "Seoul National University",
    ),
    Department(
        # life.postech.ac.kr was unreachable during development (TLS/connection failure);
        # the university's official researcher directory filtered by department is used instead.
        "postech", "POSTECH", "Pohang University of Science and Technology", "생명과학과",
        "https://www.postech.ac.kr/kor/research-industry-academia/researcher-search.do?srSearchKey=dept&srSearchVal=%EC%83%9D%EB%AA%85%EA%B3%BC%ED%95%99%EA%B3%BC",
        "Pohang University of Science and Technology",
    ),
    Department(
        # bio.unist.ac.kr was unreachable during development; the university researcher
        # directory filtered by department is used instead.
        "unist", "UNIST", "Ulsan National Institute of Science and Technology", "생명과학과",
        "https://www.unist.ac.kr/unist/research/search.do?mode=list&srSearchKey=dept&srSearchVal=%EC%83%9D%EB%AA%85%EA%B3%BC%ED%95%99%EA%B3%BC",
        "Ulsan National Institute of Science and Technology",
    ),
    Department(
        "gist", "GIST", "Gwangju Institute of Science and Technology", "생명과학과",
        "https://life.gist.ac.kr/prog/gsMember/life/P/Faculty/sub05_01_01/list.do",
        "Gwangju Institute of Science and Technology",
    ),
    Department(
        "dgist", "DGIST", "Daegu Gyeongbuk Institute of Science and Technology", "뉴바이올로지학과",
        "https://www.dgist.ac.kr/prog/peopleProfsr/newbiology/sub02_01/list.do",
        "Daegu Gyeongbuk Institute of Science and Technology",
    ),
]

DEPT_BY_UNIV = {d.univ: d for d in DEPARTMENTS}


def require_mailto() -> str:
    if not OPENALEX_MAILTO or "@" not in OPENALEX_MAILTO:
        raise SystemExit(
            "OPENALEX_MAILTO가 설정되지 않았습니다. 프로젝트 루트의 .env 파일에 "
            "OPENALEX_MAILTO=you@example.com 을 넣거나 환경변수로 지정하세요."
        )
    return OPENALEX_MAILTO
