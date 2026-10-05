# Lab Atlas — 실행 계획 (PLAN)

국내 6개 생명과학 학과의 연구실을 논문 데이터 기반으로 탐색·비교하는 정적 웹사이트.
이 문서는 기술 스택, 폴더 구조, 데이터 스키마, 단계별 실행 명령을 정리합니다.

---

## 1. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 파이프라인 | Python 3.11+ / venv + `requirements.txt` | Windows에서 별도 빌드 도구 없이 동작. `make` 대신 `python -m pipeline.run` |
| HTTP | `requests` + `truststore` | `truststore`는 OS(Windows) 인증서 저장소를 사용 → 브라우저와 같은 TLS 동작. 일부 학과 사이트의 불완전한 인증서 체인 대응 |
| HTML 파싱 | `beautifulsoup4` + `lxml` | 학과별 파서 |
| 문자열 매칭 | `rapidfuzz` | 이름·논문 제목 유사도 |
| 스키마 | `pydantic` v2 (Python) / TypeScript 타입 (프론트) | 파이프라인 마지막 단계에서 검증 |
| 임베딩·클러스터링 (3단계) | `sentence-transformers` (`allenai-specter`, CPU), `networkx` Louvain, `umap-learn`, `scikit-learn` | `requirements-ml.txt`로 분리 (무거운 의존성) |
| 프론트엔드 | Vite + React + TypeScript, `react-force-graph-2d`, `react-router-dom` (HashRouter) | GitHub Pages 정적 호스팅 호환 |
| 배포 | GitHub Actions → GitHub Pages | 6단계에서 워크플로 작성 |

외부 데이터 소스
- 각 학과/대학 공식 교수진 페이지 (HTML)
- OpenAlex API (`api.openalex.org`) — `mailto` 파라미터 필수(polite pool), 초당 최대 5회로 제한. 일일 크레딧 한도가 있어(키 없음 $0.1/일, 무료 API 키 $1/일, 검색 1회 = 10 크레딧) `.env`/`local.env`에 `OPENALEX_API_KEY`를 둡니다. 한도 소진(429 + 긴 Retry-After) 시 파이프라인은 즉시 중단하며, 캐시 덕분에 재실행하면 이어서 진행합니다
- Semantic Scholar Graph API — 논문 TLDR (선택, 실패해도 진행)

사이트는 런타임에 어떤 API도 호출하지 않습니다. 모든 데이터는 빌드 시 JSON으로 고정됩니다.

---

## 2. 폴더 구조

```
lab-atlas/
├─ PLAN.md
├─ README.md                      # 6단계
├─ .env.example                   # OPENALEX_MAILTO, S2_API_KEY(선택)
├─ pipeline/
│  ├─ requirements.txt            # 2단계 의존성
│  ├─ requirements-ml.txt         # 3단계 의존성
│  ├─ config.py                   # 학과 목록, 기간, 선정 기준, 속도 제한
│  ├─ schemas.py                  # pydantic 스키마 (중간 산출물 + 웹 데이터)
│  ├─ run.py                      # 오케스트레이터: python -m pipeline.run
│  ├─ step01_faculty.py           # 교수진 페이지 수집
│  ├─ step02_institutions.py      # OpenAlex 기관 ID 확인
│  ├─ step03_match.py             # 교수 ↔ OpenAlex 저자 매칭 (원칙 3)
│  ├─ step04_papers.py            # 최근 5년 논문 수집 + 기준 판정
│  ├─ step05_tldr.py              # Semantic Scholar TLDR 보강
│  ├─ step06_stats.py             # 요약 통계
│  ├─ validate.py                 # 스키마 검증
│  ├─ lib/
│  │  ├─ http.py                  # 캐시·속도 제한·재시도 HTTP 클라이언트
│  │  ├─ openalex.py              # OpenAlex 호출 래퍼
│  │  ├─ names.py                 # 이름 정규화·로마자 성씨 변형
│  │  ├─ textutil.py              # 초록 복원, 제목 정규화
│  │  └─ faculty/                 # 학과별 파서 (kaist, snu, postech, unist, gist, dgist)
│  ├─ tests/                      # 파서·매칭 단위 테스트
│  ├─ cache/                      # 모든 HTTP 응답 캐시 (git 제외)
│  └─ output/                     # 산출물
│     ├─ faculty.json             # 교수진 페이지 수집 결과
│     ├─ institutions.json        # OpenAlex 기관 ID
│     ├─ matches.json             # 매칭 결과 + 근거
│     ├─ excluded.csv             # 제외된 PI: 이름, 대학, 사유, 후보 ID
│     ├─ papers_raw.jsonl         # 논문 원자료(초록 포함, 사이트 비공개)
│     ├─ lab_status.json          # 기준 충족 여부
│     ├─ tldr.json                # S2 TLDR
│     └─ stats.json / stats.md    # 요약 통계
├─ web/
│  ├─ package.json                # npm scripts (dev/build/typecheck/preview)
│  ├─ public/data/                # labs.json, papers.json, edges.json, clusters.json, meta.json
│  └─ src/
│     ├─ types/data.ts            # 웹 데이터 TypeScript 타입
│     └─ ...                      # 5단계
└─ docs/screenshots/              # 6단계
```

---

## 3. 범위와 선정 기준

- 대상 학과: KAIST 생명과학과, 서울대 생명과학부, POSTECH 생명과학과, UNIST 생명과학과, GIST 생명과학과(구 생명과학부), DGIST 뉴바이올로지학과
- 대상: 각 학과 교수진 페이지에 **현재 전임교원**으로 등재된 교수 (명예·겸임·초빙·강의·연구교수 제외)
- 기간: "최근 5년" = 수집 연도 포함 5개 연도 (2026년 수집 시 2022–2026)
- 기준: 위 기간 동안 **마지막 저자 또는 교신저자**인 논문(OpenAlex type이 `article` 또는 `review`) **5편 이상**
- 분석용 논문 집합(CP1 결정, 옵션 C): 기준 판정은 PI 프로필의 전체 논문으로 하되, 유사도·키워드·클러스터링·대표 논문에는 PI 저자 항목의 소속이 현 기관이거나 미기재인 논문(`pi_roles[*].at_home_institution`)만 사용. OpenAlex 병합 프로필에 섞인 동명이인 논문을 분석에서 배제하면서, 이전 기관에서 낸 논문으로 기준을 충족한 신임 PI는 유지하기 위함
- 주제 검증은 OpenAlex Life Sciences 도메인 비율 ≥ 40% 유지(CP1 결정; Health Sciences 미포함)
- 동명이인 논문 검토(CP2 결정, 옵션 B): 같은 기관·소속 미기재의 동명이인 논문은 위 필터로 걸러지지 않으므로, 기준 충족 연구실의 모든 논문을 SPECTER로 임베딩해 연구실 중심(분석용 논문 임베딩의 중앙값)과의 코사인이 0.70 미만인 논문을 `output/paper_flags.csv`로 표시하고, 제목·학술지를 사람이 검토해 PI 연구 분야와 명백히 다른 분야(임상의학, 공학, 재료, 사회과학, 인문학, 작물 육종 등)인 논문만 `pipeline/curation/excluded_papers.csv`에 사유와 함께 기록. 생명과학 공동연구·방법론 가이드·리뷰·사설은 유지. 제외 논문은 기준 판정과 분석 모두에서 빠짐(2026-10 수집분: 267편 표시 → 229편 제외, 38편 유지; 이로 인해 2개 연구실이 기준 미달로 전환)
- 목표 규모: 60–120개 연구실

---

## 4. 데이터 스키마

Python: `pipeline/schemas.py` (pydantic). TypeScript: `web/src/types/data.ts`. 둘은 1:1로 대응합니다.
모든 레코드에 출처 URL과 수집 날짜(`retrieved_at`, ISO 날짜)를 둡니다. 확인할 수 없는 필드는 `null`(화면에는 "정보 없음").

### 공통
```
Source        { url: string, kind: "faculty_page"|"faculty_detail"|"openalex_author"|"openalex_works"|"semantic_scholar"|"homepage", retrieved_at: date }
```

### labs.json — `Lab[]`
| 필드 | 타입 | 설명 |
|---|---|---|
| id | string | `"{univ}-{openalex_id}"` (예: `kaist-A5012345678`) — 이름 변경에도 안정적 |
| univ | `"kaist"|"snu"|"postech"|"unist"|"gist"|"dgist"` | |
| univ_name_ko / dept_name_ko | string | |
| pi_name_ko | string \| null | |
| pi_name_en | string \| null | 교수진 페이지 표기, 없으면 OpenAlex display_name |
| position | string \| null | 정규화된 직위 (교수/부교수/조교수) |
| lab_name | string \| null | |
| homepage_url / faculty_page_url | string \| null / string | |
| openalex_id | string | `A…` |
| orcid | string \| null | OpenAlex에 기록된 ORCID |
| match_confidence | `"high"|"medium"` | 매칭 근거 강도 |
| paper_count_5y | int | 최근 5년 article+review 수 |
| senior_paper_count_5y | int | 그중 마지막/교신저자 수 |
| keywords | string[] | 상위 OpenAlex topics |
| cluster_id | int \| null | 3단계 |
| x, y | number \| null | UMAP 초기 좌표 (3단계) |
| intro_ko | string \| null | 4단계 직접 작성 |
| representative_paper_ids | string[] | 최대 3, 4단계 |
| keyword_timeline | `{year:int, keywords:string[]}[]` | 연도별 주요 키워드 |
| sources | Source[] | |

### papers.json — `Paper[]` (초록 원문 미포함)
| 필드 | 타입 | 설명 |
|---|---|---|
| id | string | OpenAlex work ID `W…` |
| lab_ids | string[] | 데이터셋 내 저자로 참여한 연구실 |
| title | string | |
| year | int | |
| venue | string \| null | |
| doi | string \| null | `https://doi.org/...` |
| cited_by_count | int | 수집 시점 |
| type | string | article/review |
| pi_roles | `{lab_id: {position:"first"|"middle"|"last", is_corresponding:bool}}` | |
| has_abstract | bool | |
| has_tldr | bool | |
| topics | `{id, name, score}[]` | |
| summary_ko | `PaperSummary \| null` | 4단계: one_line, background, methods, findings, significance |
| openalex_url | string | |
| retrieved_at | date | |

내부 전용 `papers_raw.jsonl`에는 위 필드 + `abstract`(inverted index 복원), `tldr`, `coauthor_ids`가 추가됩니다. 이 파일은 사이트에 배포하지 않습니다.

### edges.json — `Edge[]`
| 필드 | 타입 | 설명 |
|---|---|---|
| source / target | string | lab id (source < target 사전순) |
| type | `"similarity"|"coauthor"` | |
| weight | number | 코사인 유사도 / 공동 논문 수 |
| reasons | string[] | 공통 키워드 최대 3 (similarity) |
| paper_ids | string[] | 공동 논문 (coauthor) |

### clusters.json — `Cluster[]`
| 필드 | 타입 |
|---|---|
| id | int |
| label_ko | string |
| keywords | string[] |
| size | int |

### meta.json — `Meta`
`generated_at`, `data_retrieved_at`, `window_years`(예: [2022, 2026]), `min_senior_papers`, `louvain_resolution`, `louvain_seed`, `similarity_k`, `similarity_threshold`, `counts{labs, papers, edges_similarity, edges_coauthor}`.

---

## 5. 매칭 방법 (원칙 3: 동명이인 방지)

후보 수집
1. **이름 검색**: 영문 이름 변형(어순, 하이픈 제거)으로 `/authors?search=` + `filter=affiliations.institution.id:{기관}`.
2. **논문 앵커**: 교수진 페이지에 대표 논문이 있으면(서울대·POSTECH·GIST) 제목으로 `/works?search=` → 제목 유사도 확인 → 해당 기관 소속 저자를 후보에 추가. 영문 이름이 없는 POSTECH은 이 방식이 주 경로입니다.

후보 검증 (모두 응답 데이터로만 판정)
- 소속: OpenAlex `affiliations`에 해당 기관이 최근 3년 내 연도로 존재
- 이름: 영문 이름 토큰 집합 일치(어순 무관, 하이픈·공백 무시, 중간 이니셜 허용). OpenAlex `display_name` 기준이며, `display_name_alternatives`(병합 프로필에 타인 이름이 섞임)는 앵커 ≥ 1일 때만 인정
- 영문명이 없을 때(POSTECH 등): 한글 성 + 이름의 로마자 표기 일치. 이름은 음절별 표기 변형(국어의 로마자 표기법, McCune–Reischauer, 관용 표기: 영→young/yeong, 우→woo/u 등)으로 비교. 이름이 이니셜뿐이면 성만으로 판정하되 앵커 ≥ 2 필요
- 주제: 상위 topics 중 Life Sciences 도메인 비율 ≥ 40%
- 앵커: 교수진 페이지 논문의 저자로 확인된 횟수
- ORCID: 교수진 페이지에 ORCID가 있으면 최우선

판정
- 강한 후보 = 소속 ✔ + 이름 ✔ + (주제 ✔ 또는 앵커 ≥ 1)
- 강한 후보가 정확히 1명 → 매칭 (`high`: ORCID 또는 앵커 ≥ 1 / `medium`: 그 외)
- 여러 명 → 앵커가 한 명만 가리키면 그 후보, 한 후보의 앵커가 3 이상이고 다른 모든 후보의 2배 이상이면 그 후보, OpenAlex의 동일인 분할 프로필(같은 이름·ORCID 충돌 없음·작은 쪽 works 수 ≤ 큰 쪽의 10%)이면 큰 쪽 선택, 그 외에는 **제외**
- 0명 → **제외**
- 제외 시 `excluded.csv`에 이름, 대학, 사유 코드, 후보 ID와 근거 기록

---

## 6. 단계별 실행 명령 (Windows PowerShell 기준)

```powershell
# 0) 준비 (최초 1회)
cd lab-atlas
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r pipeline\requirements.txt
copy .env.example .env   # OPENALEX_MAILTO 입력

# 2단계: 데이터 수집 (캐시 덕분에 재실행 시 네트워크 재요청 없음)
python -m pipeline.run --stage collect
#   개별 단계: python -m pipeline.run --steps faculty,institutions,match,papers,tldr,stats,validate

# 3단계: 유사도·클러스터링
pip install -r pipeline\requirements-ml.txt
python -m pipeline.run --steps flag                # 동명이인 의심 논문 표시 → output/paper_flags.csv
#   검토 결과를 pipeline/curation/excluded_papers.csv에 기록한 뒤 수집 결과에 반영:
python -m pipeline.run --steps papers,tldr,stats
python -m pipeline.run --stage analyze            # embed → analyze → validate
#   클러스터 라벨: pipeline/curation/cluster_labels.json (키워드가 바뀌면 경고 → 재검토)

# 4단계: 대표 논문 선정 + 요약 반영 + 웹 데이터 내보내기
python -m pipeline.run --stage export             # select → export → validate
#   select: output/representatives.json + output/summary_tasks/batch_NN.md(초록·TLDR, 작성용)
#   한국어 요약·연구실 소개: pipeline/curation/summaries/batch_*.json ({"labs": {...}, "papers": {...}})
#   요약이 없는 논문·연구실은 null로 내보내고 사이트에 "정보 없음"으로 표시. 작성 현황은 meta.json의 summary_coverage
#   (2026-10 기준: 대표 논문 311편 중 117편, 연구실 소개 106개 중 40개 작성 — batch 05~11 미작성)

# 5~6단계: 프론트엔드
cd web
npm install
npm run dev          # 개발 서버
npm run typecheck
npm run build        # 정적 빌드 → web/dist
npx vite preview --port 4173; node scripts/check.mjs   # 스크린샷 + 호버 FPS (실데이터 / ?dummy=300)

# 6단계: 검증 (캐시 없이 실시간 요청)
cd ..
python -m pipeline.run --stage verify   # validate → fields(빈 필드 통계) → links(깨진 링크) → spotcheck(무작위 10곳 대조)
#   산출물: output/field_stats.md, output/link_report.csv, docs/verification.md
#   배포: .github/workflows/deploy.yml (main push → 검증 → 빌드 → GitHub Pages)
```

테스트: `python -m pytest pipeline/tests`

---

## 7. 체크포인트

| 단계 | 산출물 | 체크포인트 |
|---|---|---|
| 1 기획 | PLAN.md, 스키마, 골격 | — |
| 2 수집 | faculty/matches/papers/stats, excluded.csv | **[CP1]** 통계 보고, 40개 미만·150개 초과 시 기준 조정안 |
| 3 분석 | edges, clusters, 좌표 | **[CP2]** 클러스터 라벨 검토 |
| 4 요약 | 대표 논문·요약·소개 | 요약 10개 무작위 대조 보고 |
| 5 프론트 | web/ | 실제 + 더미 300 노드 성능 확인 |
| 6 검증 | 링크 검사, 스크린샷, 워크플로, README | 무작위 10개 연구실 대조표 |
