# Lab Atlas Korean–English search implementation plan

Planning date: **2026-11-20**. Inspected branch: **`main`**. Inspected commit: **`8d4d0496efbde3a5c222bec5bf5a59f97059e024`** (`F1: bilingual search with keyboard-layout correction`).

This document began as the implementation plan. During planning, only read-only inspection was performed. The user subsequently authorized implementation; the progress record below distinguishes completed engineering work from outstanding validation.

The initial inspection at `0fba910b6afd4122bd2d447f1379c16a094382c9` is superseded by the commit above. In particular, the earlier 498-lab dataset and descriptions of separate search implementations are obsolete. No `AGENTS.md` was found in the repository (including hidden paths) or applicable ancestor directories. Recheck instructions and working-tree changes before implementation. The unrelated untracked `docs/openalex-first-design.md` must be preserved.

The existing root planning document is preserved in full in the historical appendix. Windows treats `plan.md` and the Git-tracked `PLAN.md` as the same path (`core.ignorecase=true`); the working-tree filename is `plan.md`. Do not create two case-only variants or stage an unrelated rename. Existing references to `PLAN.md` concern the historical document. All design choices below are **proposals**, except the explicitly verified findings in section 2; assumptions and release dependencies are in section 11.

## 1. Goal, scope, and non-goals

Deliver one predictable search experience for explorer suggestions, graph matches, explorer list results, and shortlist **관심사로 찾기**. The same dataset, query, and filters must produce the same complete ranked lab IDs and evidence on all surfaces. Suggestions and pagination are projections of this result, never independent matching implementations.

Required release: reviewed bilingual concept matching, coherent phrases, all-term coverage, useful relevance ordering, truthful explanations, consistent filters, access to every result, Korean IME handling, keyboard accessibility, restorable hash-router URLs, and measured performance. Retain the current static Vite/React deployment, current public data, shortlist recommendations/comparison, graph interactions, and the existing keyboard-layout correction feature.

Non-goals: runtime translation, broad typo tolerance, arbitrary natural-language interpretation, guessed romanized identities, collection of more universities, changing shortlist recommendation scores, rebuilding graph embeddings, or adding a backend/vector database/hosted search service. Search relevance expresses fit to a query, never lab quality. Compact exported indexes, lazy paper loading, and compatible semantic retrieval are separate future work (section 13).

## 2. Verified current architecture

### 2.1 Source findings at the inspected commit

| File / function | Verified behavior and implication |
|---|---|
| `web/src/lib/search.ts`: `buildSearchIndex`, `searchLabs`, `run`, `bestHit`, `matcher`, `fromKeyboard` | A shared engine already exists. Index entries keep raw names, introductions and title strings; keywords combine lab keywords, keyword timelines and the 12 most frequent paper topics per lab. Cluster/subcluster labels are searchable. Titles lose paper IDs. Names also include university/department names. |
| Same file: `norm`, `matcher` | Non-Latin/general matching uses lowercase + NFC and removes spaces, several dashes and punctuation. Latin alphanumeric matching requires a word start only. Punctuation such as `,` can normalize to an empty substring. Normalized document text is recomputed during matching. |
| Same file: `run`, `bestHit` | Every whitespace-separated query word must match somewhere in a lab's records. Best field weights are name 6, keyword 4, cluster 3, intro 2, title 1; ties use descending `paper_count_5y`. Words can match unrelated papers. Variant order can select a literal title before a translated keyword. Explanations describe only the first query word. |
| Same file: `Terms`, `wordKo`, `variants` | Existing English-label → Korean-renderings dictionary is used asymmetrically. Reverse lookup is limited to keys reduced to a single English word. Korean alias lookup is gated on Hangul, so Latin abbreviations in translation arrays are not reliably used as aliases. No stable concept IDs or equal-language-ranking guarantee. |
| Same file: `fromKeyboard`, `searchLabs` | Two-set Korean keyboard conversion already exists. If the global as-typed search is empty, it tries joined Latin words and then per-word corrections. This is keyboard-layout correction, not general typo correction. |
| `web/src/data/DataContext.tsx`: `buildAtlas`, `DataProvider` | `Atlas.searchIndex()` lazily builds and caches one index per Atlas instance. Six JSON files load eagerly through `Promise.all`; optional `search_terms.json` errors fall back to `{}`. Dummy mode still fetches real data first, then builds synthetic labs with no papers. Preserve this useful per-load cache. |
| `web/src/data/explore.tsx`: `ExploreProvider`, `passesFilters` | `matchesQuery` has been removed. State is in memory. Filters use OR within university/discipline/cluster sets and AND across sets; an empty set means all. Multi-discipline labs match any selected discipline. |
| `web/src/components/SearchBox.tsx` | Calls the shared engine itself, filters against supplied `labs`, takes eight ranked results, and shows reasons. Filtering occurs before its slice, but its parent still supplies all labs. ArrowDown with zero results can set active index to -1; later changing results can leave an invalid index. Enter has no composition guard. Existing combobox/listbox roles are a starting point. |
| `web/src/components/Toolbar.tsx` | Supplies `atlas.labs` to SearchBox; active explorer filters are not passed to suggestions. One `shown` count represents different things in graph/list mode. |
| `web/src/pages/ExplorePage.tsx` | Calls shared `searchLabs` for global matched IDs, separately filters labs, and creates list rows by dataset order. Graph receives filtered labs and matched IDs. Shared matching exists, but there is no single filtered ranked result object for the page. |
| `web/src/components/ListView.tsx` | Defaults to descending papers and re-sorts incoming labs. No relevance sort. All incoming rows are currently reachable. |
| `web/src/pages/ShortlistPage.tsx`: `useSearch`, `SearchSection` | Local matcher is gone; `useSearch` delegates to shared search. Query is local component state. Only 12 results are rendered, with no next page. Existing Korean copy claims translation and keyboard correction. |
| Same file: `Recommendations`, `Compare`, sharing actions | Recommendations use lazily loaded lab vectors, have independent field filtering, and exclude `mixed_topics`/`wrong_field`. Keep them separate from search. `labs` URL parameter opens a shared shortlist without overwriting local storage. Two `setParams({})` calls would erase new search parameters. |
| `web/src/components/GraphView.tsx`: `forced`, `isLit` | Search matches get display priority; hovered/selected labs, neighbors, selected edges and trends can temporarily take visual priority over search. Preserve layout/node reuse, edge modes and selection behavior. Test matched IDs separately from transient canvas brightness. |
| `web/src/App.tsx`, `web/vite.config.ts` | HashRouter and relative Vite base support static subpaths. ExploreProvider is already **inside** HashRouter; its “above the router” comment is stale. URL hooks can be used without moving it. |
| `web/src/types/data.ts` | Eleven `Univ` values, five `Discipline` values; bilingual PI fields, optional lab name, introductions, timelines, paper IDs/topics/roles and quality flags exist. Public papers contain no abstract/TLDR text. |

### 2.2 Export, vocabulary, and data quality

`pipeline/step10_export.py:run` exports paper associations only for retained labs satisfying `pipeline/lib/selection.py:in_analysis_set` (home institution or no listed institution). `pipeline/step04_papers.py` applies reviewed `(lab_id, paper_id)` exclusions from `pipeline/curation/excluded_papers.csv` before export. These are association exclusions, not necessarily global paper deletions.

`pipeline/search_terms.py:vocabulary/translate/run` collects lab/timeline terms and paper topic/subfield labels, generates Korean renderings using an external API during curation, and caches them. The committed curation has **3,093 English keys**; `step10_export.py:export_search_terms` exports the present vocabulary, **2,832 keys / 5,369 renderings**. This release must use committed files and human review; running that translation script or calling its API is unnecessary.

Existing renderings include shortened and compound topic labels. They are useful review candidates, **not a ready-made synonym graph**. For example, a broad label containing data mining and machine learning must not make data mining and machine learning interchangeable. Preserve the existing translation fallback explicitly during migration (section 6).

`Lab.intro_unavailable` exposes `insufficient_papers`, `mixed_topics`, and `wrong_field`. `match_confidence` is high/medium, not a per-paper truth label. `vector_paper_count` describes vector support, not search relevance. `pipeline/curation/intro_unavailable.json` also has a `review` map (28 currently exported lab IDs), but its notes are **not** exported to the browser. Do not claim that the runtime engine can use those notes or identify a particular incorrect paper from a lab-level flag.

### 2.3 Current data and tooling

Read-only counts: **852 labs, 17,712 papers, 11 universities, five disciplines**; meta generated **2026-11-19**, retrieved **2026-11-16**, publication window 2022–2026. Discipline memberships are life 165, chem 208, phys 157, math 130, cs 194; these total 854 because some labs have multiple disciplines. There are 813 introductions and 39 unavailable flags: 23 mixed topics, 14 insufficient papers, two wrong field.

| Eager public file | Bytes on disk |
|---|---:|
| `labs.json` | 3,235,862 |
| `papers.json` | 27,690,372 |
| `edges.json` | 1,576,957 |
| `clusters.json` | 37,706 |
| `meta.json` | 16,210 |
| `search_terms.json` | 293,866 |
| **Total** | **32,850,973** |

These are uncompressed file sizes, not measured network transfer or browser heap. Re-measure on a changed dataset. Fingerprints for benchmark provenance:

- `labs.json` SHA-256: `5f1d702a1639fc3eeaf4e9425f5a48f62b381d29377e49558be5d13df69d82b7`.
- `papers.json` SHA-256: `5c1ec5aa4e25567c227b969034d830d049c7d0093e40f41569c3c155fd72bd8f`.

`web/package.json` has `dev`, `typecheck`, `build`, `preview`; **no test script or frontend unit runner**. Dependencies include React 18, react-router-dom 6, TypeScript 5.6 and Vite 5. `playwright-core` is already a dev dependency. `web/scripts/check.mjs` launches installed Microsoft Edge, captures screenshots and hover FPS; it is not a search assertion suite. `shot.mjs` is an ad-hoc screenshot helper. Python uses pytest; CI runs pipeline tests and data validation, then frontend typecheck/build. `web/node_modules` was absent during inspection. Existing commands and proposed additions are separated in section 9.

## 3. Current behavior versus intended behavior

| Current | Required result |
|---|---|
| Shared engine but three separately projected searches | One filtered, ranked `SearchResponse` for explorer; same engine/options on shortlist |
| Keyword translations depend on query language and word splitting | Reviewed aliases become the same concept IDs in queries and documents; equal scores/order for equivalent concept-only queries |
| Whitespace splits `graph neural network` into independent words | Longest reviewed phrases are atomic; unknown quoted phrases stay atomic |
| Terms across unrelated papers qualify without qualification | All units required; coherent records outrank scattered coverage, which is explicitly labeled |
| Substring/prefix accidents and empty normalized strings | Boundary-aware Latin tokens, scoped Korean spacing, punctuation-only input gives guidance |
| Paper-count ties, list overrides engine order | Explicit ranking tiers, capped contributions, stable lab-ID ties; relevance default during searches |
| First-word reason and title without ID | Evidence covering every requested unit, with original field text and paper IDs |
| Global fallback and suggestions ignore filters | Apply filters before eligibility, correction fallback and presentation limits |
| Eight suggestions / twelve shortlist rows | Suggestions link to full explorer results; shortlist supports incremental “더 보기” |
| In-memory query/filter state | Validated hash-route parameters, reload/back/forward/shared-link restoration |
| Composition Enter can pick; selection can become invalid | Composition-safe input, valid active descendants, predictable zero-result keyboard behavior |

## 4. Proposed architecture and TypeScript contracts

Refactor the existing engine, retaining the public import boundary during PR 1. The target layout is `web/src/lib/search/{types,normalize,keyboard,concepts,index,query,rank}.ts` and `web/src/data/useLabSearch.ts`. Put filter helpers in `query.ts`; avoid an extra framework or generic search DSL. `keyboard.ts` houses the existing converter with characterization tests. Remove the old `web/src/lib/search.ts` only after migrating its exports/callers; TypeScript can otherwise resolve the old file before the new directory.

The contracts below are proposed implementation targets, not existing APIs. Import `Lab`, `Paper`, `Cluster`, `Discipline`, `Univ` from `types/data`. Internal mutable builders may be used, but exposed indexes and arrays are readonly.

```ts
type ConceptId = string;
type UnitId = string;
type RecordId = string;
type SearchField =
  | 'pi_name_ko' | 'pi_name_en' | 'lab_name' | 'university' | 'department'
  | 'keyword' | 'timeline_keyword' | 'intro' | 'paper_title'
  | 'paper_topic' | 'cluster' | 'subcluster' | 'translated_label';
type EvidenceQuality = 'ordinary' | 'mixed_topics' | 'wrong_field';

interface SearchFilters {
  univs: ReadonlySet<Univ>;
  fields: ReadonlySet<Discipline>;
  clusters: ReadonlySet<number>;
}
interface SearchDataset {
  version: string; // export date + counts for diagnostics, not a sole cache key
  labs: readonly Lab[];
  papers: readonly Paper[];
  clusters: readonly Cluster[];
  legacyTerms: Readonly<Record<string, readonly string[]>>;
}
interface ConceptAlias {
  text: string;
  language: 'ko' | 'en' | 'scientific';
  kind: 'phrase' | 'abbreviation';
  // Korean optional spaces only at these reviewed segment boundaries.
  hangulSegments?: readonly string[];
  // Required for ambiguous abbreviation expansion; all guards apply.
  guard?: { anyConceptIds: readonly ConceptId[] };
}
interface SearchConcept {
  id: ConceptId;
  labelKo: string;
  labelEn: string;
  disciplines: readonly Discipline[]; // documentation, not automatic filtering
  aliases: readonly ConceptAlias[];
  relatedIds: readonly ConceptId[]; // never used as synonym expansion
  sourceExamples: readonly { labId: string; field: SearchField; paperId?: string; text: string }[];
  review: { status: 'draft' | 'approved'; reviewer: string | null; date: string | null; note: string };
}
interface ConceptDictionary {
  version: string;
  concepts: readonly SearchConcept[]; // runtime compiler accepts approved entries only
}
interface NormalizedText {
  folded: string;
  // Segment changes preserve sentence/punctuation barriers for phrase matching.
  tokens: readonly { text: string; segment: number }[];
}
interface IndexedRecord {
  id: RecordId;
  labIds: readonly string[];
  field: SearchField;
  originalText: string;
  normalized: NormalizedText;
  conceptIds: ReadonlySet<ConceptId>;
  paperId?: string;
  year?: number;
  sourceRecordId?: RecordId; // translation/topic provenance
}
interface LabDocument {
  lab: Lab;
  recordIds: readonly RecordId[];
}
interface SearchIndex {
  datasetVersion: string;
  dictionaryVersion: string;
  labs: ReadonlyMap<string, LabDocument>;
  records: ReadonlyMap<RecordId, IndexedRecord>;
  concepts: ReadonlyMap<ConceptId, ReadonlySet<RecordId>>;
  tokens: ReadonlyMap<string, ReadonlySet<RecordId>>;
  dictionary: ConceptDictionary;
}
type QueryUnit =
  | { id: UnitId; kind: 'concept'; conceptId: ConceptId }
  | { id: UnitId; kind: 'literal'; normalized: string }
  | { id: UnitId; kind: 'phrase'; tokens: readonly string[] };
interface ParsedQuery {
  raw: string;
  normalized: string;
  state: 'empty' | 'invalid' | 'ready';
  units: readonly QueryUnit[];
  key: string; // canonical IDs/units, independent of alias language
  notices: readonly string[]; // codes, translated by UI
}
interface MatchEvidence {
  unitIds: readonly UnitId[];
  recordId: RecordId;
  field: SearchField;
  conceptIds: readonly ConceptId[];
  originalText: string;
  paperId?: string;
  sourceRecordId?: RecordId;
  method: 'exact_name' | 'concept' | 'literal' | 'phrase' | 'legacy_translation';
  quality: EvidenceQuality; // evaluated for this lab-record association
  span?: { start: number; end: number }; // only verified original UTF-16 offsets
}
interface LabMatch {
  labId: string;
  exactName: boolean;
  evidence: readonly MatchEvidence[];
  coveredUnitIds: ReadonlySet<UnitId>;
  requiresQuestionableEvidence: boolean;
  cautions: readonly ('mixed_topics' | 'wrong_field' | 'limited_papers')[];
}
interface SearchResult {
  labId: string;
  score: number;
  tier: 1 | 2 | 3 | 4 | 5;
  evidence: readonly MatchEvidence[];
  coverage: 'single_record' | 'scattered';
  cautions: readonly ('mixed_topics' | 'wrong_field' | 'limited_papers')[];
}
interface SearchResponse {
  query: ParsedQuery;
  eligibleLabIds: readonly string[]; // filters only, including empty query
  results: readonly SearchResult[]; // complete ordered result; no hidden engine limit
  matchedIds: ReadonlySet<string>;
  total: number;
  unfilteredTotal?: number; // count for the same applied interpretation
  correction?: { original: string; applied: string; kind: 'keyboard_layout' };
}

function normalizeText(text: string): NormalizedText;
function compileConcepts(dictionary: ConceptDictionary): ConceptDictionary;
function buildSearchIndex(data: SearchDataset, dictionary: ConceptDictionary): SearchIndex;
function interpretQuery(raw: string, dictionary: ConceptDictionary): ParsedQuery;
function passesSearchFilters(lab: Lab, filters: SearchFilters): boolean;
function filterLabIds(index: SearchIndex, filters: SearchFilters): readonly string[];
function collectLabMatch(index: SearchIndex, labId: string, query: ParsedQuery): LabMatch | null;
function rankLabMatch(match: LabMatch, query: ParsedQuery): SearchResult;
function compareResults(a: SearchResult, b: SearchResult): number;
function searchLabs(index: SearchIndex, raw: string, filters: SearchFilters,
  options?: { keyboardCorrection?: boolean; includeUnfilteredCount?: boolean }): SearchResponse;
function useLabSearch(query: string, filters: SearchFilters,
  options?: { keyboardCorrection?: boolean; includeUnfilteredCount?: boolean }): SearchResponse;
```

`compileConcepts` can use private compiled matchers/maps alongside the declared dictionary; do not recompile aliases in a query loop. `LabMatch` includes coverage evidence before presentation truncation. A complete exact-name equality may satisfy the full raw query as identity intent even if its words are also dictionary aliases. Partial name matches must satisfy the normal all-unit policy.

Keep `Atlas.searchIndex()`'s current lazy closure. Its captured immutable dataset and dictionary versions define the cache lifetime; a new Atlas load builds a new index, even if dates/counts happen to match. Do not use a global cache keyed only by `generated_at`, or `useMemo` in each search component to build indexes. `useLabSearch` memoizes query/filter computation against the stable Atlas/index and canonical filter key; changing sort, hover, open filter rows or route must not rebuild it. No memo key based on freshly allocated Set/object identity alone.

The explorer calls the hook once and gives Toolbar/SearchBox the first eight `SearchResult`s plus `total`, while ListView receives the full ranked result and GraphView receives `matchedIds ∩ eligibleLabIds`. Shortlist calls the same hook with explicit filters (initially all); it never inherits hidden explorer filters or recommendation filters.

## 5. Query processing, indexing, normalization, and ranking rules

### 5.1 Normalization and parsing

1. Preserve every original string. Use Unicode NFKC for matching, lowercase Latin consistently, trim and collapse whitespace. Preserve meaningful symbols/Greek letters and record boundaries; establish fixtures for scientific strings such as `CO2`, `α-synuclein`, `C++` before choosing token splitting. Never remove all punctuation or whitespace from the entire corpus.
2. Latin word matching requires both token boundaries. `RNA` matches an `RNA` token and the `RNA` component of `RNA-sequencing`; it does not match `internal`, `journal`, or `RNase`. No automatic stemming/prefix expansion. Explicit scientific variants/plurals belong in reviewed aliases. Hyphens/dashes can separate phrase tokens; arbitrary intervening words cannot.
3. For reviewed Korean aliases, permit optional whitespace at explicitly reviewed segment boundaries, e.g. `['기계','학습']`; `기계학습` and `기계 학습` identify one concept. Do not merge across punctuation, field boundaries, paper boundaries, or arbitrary English words. Unknown Korean text uses literal Hangul-run matching, not unrestricted space removal across a sentence. No Korean morphology library in the initial release.
4. Recognize approved concepts in both source records and queries, longest phrase first. Reject conflicting approved normalized aliases during dictionary compilation; allow a shared spelling only with non-overlapping explicit guards, otherwise leave it literal. Stable concept ID can order equivalent matches after ambiguity has been resolved, never choose a meaning silently. Consume overlapping spans once. `graph neural network` becomes one concept, not graph + neural + network; the same applies to its reviewed Korean equivalent. Nested broader concepts are not automatically added. Non-overlapping, explicitly requested concepts remain separate AND units.
5. Quoted phrases outside the dictionary are atomic ordered contiguous token sequences in one record. Unquoted residual words become literal units, each required. Preserve unknown terms; do not silently drop stopwords or expand broader/related concepts. Recognized alias spans are replaced by IDs rather than retained as extra literal requirements.
6. Mixed-language queries combine canonical concepts and remaining literals under the same AND rule, e.g. `단백질 구조 deep learning` requires both concepts. Deduplicate repeated units, so repeating a term or its bilingual alias does not increase scores.
7. Before ordinary per-unit eligibility, compare the full query with each stored `pi_name_ko`, `pi_name_en`, and non-null `lab_name` using a dedicated name key: Unicode/case/whitespace normalization and consistent hyphen-versus-space handling. Optional Korean name spacing is allowed within this field comparison only. A whole-name equality creates one `exact_name` evidence record covering the full request, including parser units that would otherwise differ because of spacing; partial names use ordinary coverage. Preserve stored token order; no guessed initials, romanization, surname-only identity claims, or synthetic `labTitle()` fallback treated as a real lab name.
8. Empty/whitespace query means browse mode (`results=[]`, `matchedIds` empty, graph adapter supplies `null`). Punctuation-only input yields `invalid`, no matches and guidance, never “match all.” Set and document a modest query limit (proposal: 200 characters / 20 distinct units); show a validation message rather than silently dropping requirements. Unclosed quotes produce an explicit notice and a documented literal interpretation.
9. Run the as-typed interpretation against eligible labs first. Preserve keyboard conversion in a separate fallback when there are no eligible matches and there are unrecognized Latin keyboard candidates. Try joined Latin input, then per-word candidates using the existing converter. Never reinterpret a recognized scientific abbreviation/concept. All surfaces use the same chosen interpretation. Record the correction and retain the raw input/URL; do not silently rewrite the user's text. Unfiltered counts, if requested, must use the chosen interpretation; an out-of-filter hit must not suppress correction. Normalized unknown queries with no correction remain zero results.

### 5.2 Records and coverage

Use one record per name field, university, department, individual lab keyword, individual timeline keyword with year, introduction, individual paper title with ID, and individual paper topic with paper ID. Store a shared paper record once with associated lab IDs; quality is assessed per lab-paper association. Preserve cluster/subcluster labels as metadata records. Preserve existing translated-label lookup as explicitly attributed fallback evidence linked to its original record.

Build concept/token postings once. For Korean substring fallback, a bounded scan of pre-normalized candidate records is acceptable initially; measure before adding a specialized index. Never concatenate all paper titles, all keyword strings, or names and department into one searchable record. Do not use the existing top-12 topic aggregate as a coherence record; index deduplicated source topics with provenance at metadata weight. Repeated timeline/topic labels may be deduplicated for scoring while retaining source references.

Eligibility requires **all** query units to be covered. An atomic concept or quoted phrase must occur within one record; it cannot be assembled from individual words in separate papers. Different query units may be covered by different records, but this is `scattered` and receives tier 1. A single intro paragraph is one record; being in that paragraph is not evidence that words are an exact phrase. A name match can still coexist with research requirements; a partial PI-name token does not override a missing topic.

### 5.3 Initial relevance model (tunable hypotheses)

Use explicit tiers so publication volume cannot overwhelm stronger intent. Rank highest tier first. Every normal result already meets all-unit coverage.

| Tier | Eligibility |
|---|---|
| 5 | Full normalized query equals a stored professor or lab name; all equally exact duplicate names share this tier |
| 4 | All requested units occur as recognized concepts/contiguous phrases in one lab keyword record |
| 3 | All requested units occur as recognized concepts/contiguous phrases in one introduction or one paper title |
| 2 | All units occur together within another single record, or within one record without the stronger phrase condition |
| 1 | All units are covered only across records; label “여러 항목에서 함께 찾음” |

A single complete literal token in a keyword/title can count as a one-token phrase. For the tier-3/4 strong phrase condition, two or more adjacent residual literal query tokens must occur as an ordered contiguous group in the record, within one normalized segment; separate requested concept units may coexist within that record. Arbitrary separated residual terms qualify only for tier 2 in one record. Sentence and punctuation barriers prevent `graph. neural. network` from becoming the GNN phrase; only reviewed hyphen/spacing separators may bridge phrase tokens. University, department, cluster, timeline and paper-topic matches are metadata and cannot masquerade as a lab/professor name or promote a result above tier 2. Translated-label fallback is also limited to tier 2. Multi-unit keyword/intro matches that fail single-record coverage remain tier 1 even when one individual term is strong.

Proposed numeric score: `tier * 1000 + detailScore`. For each requested unit take only its best eligible field contribution: actual name 12, lab keyword 10, intro/title 6, timeline/paper-topic 3, affiliation/cluster 2, legacy translation 1. Let `meanWeight` be the sum divided by distinct unit count (whole-name equality uses 12); let `extraPapers` be up to two distinct ordinary-quality supporting papers beyond the selected best evidence. Compute `baseDetail = min(99, floor(90 * meanWeight / 12) + min(9, 5 * extraPapers))`. This caps paper support at nine points regardless of publication volume. For tier 1 only, use `floor(baseDetail / 2)` when required coverage depends on questionable evidence, otherwise `50 + floor(baseDetail / 2)`; other tiers use `baseDetail`. Deduplicate paper IDs; duplicate records and alias variants never contribute extra points. No paper-count, citation, venue, institution-prestige or language-specific bonus. This bounded score preserves tier precedence and defines the quality band exactly.

For concept units, only canonical ID/field/coherence/quality determines scoring. Do not add a literal bonus just because the user's alias also appears verbatim. Equivalent concept-only bilingual queries must return identical IDs, scores and order under identical filters. Tie-break with ascending lab ID using a code-unit comparator (`a < b`), never locale-dependent name sorting or paper count. Evidence selection also uses stable field priority, record ID and paper ID, independent of input array order. Keep alternative paper-count sorts as explicit UI choices.

### 5.4 Quality and truthful evidence

- `mixed_topics` / `wrong_field`: mark paper titles, paper topics, derived keywords/timelines, paper-derived cluster/subcluster labels and their translated versions as questionable associations. They may support a result, but if any required unit depends exclusively on such evidence, cap that result at tier 1 and display the corresponding caution. Within tier 1, ordinary evidence precedes questionable evidence using the numeric band above. A coherent but questionable record keeps `coverage='single_record'`; do not label it scattered merely because its tier was capped. Do not claim a particular title is false from a lab-level flag.
- Identity/affiliation matches keep normal eligibility, including exact-name tier 5, even for flagged labs. Show the lab caution without deleting valid identity results. Use unflagged evidence preferentially if it fully covers the query.
- `insufficient_papers`: retain evidence with a limited-data notice; it is not proof of an incorrect association. `match_confidence='medium'` alone does not suppress names or imply wrongdoing. Low vector support does not reduce exact text relevance.
- Validate `paper.lab_ids`, `pi_roles` and record references; do not reintroduce excluded lab-paper associations or index non-home associations. Treat absent required linkage as an index validation diagnostic, not a guessed match.
- The private `review` map remains a documented limitation. Exporting a new review flag is optional later work and needs synchronized Python/TypeScript schemas and validation; do not scrape private curation into the browser bundle in this release.

Return enough evidence to demonstrate coverage of every unit. UI can show the best record and an expandable “일치 근거” list, but must not present the first word as proof of the full query. Each title evidence carries a valid paper ID; link through its known DOI/OpenAlex URL or a lab detail anchor. If showing scattered matches, identify the separate records honestly.

Initial highlighting is deliberately simple: render the original field/phrase/whole keyword as text, emphasize a verified exact substring only when its original offsets are known, otherwise show the original record plus a concept badge such as `기계학습 ↔ machine learning`. Never apply normalized offsets to original text, bold a translated phrase absent from the source, or inject HTML. Full normalization-to-original offset mapping is optional after this truthful display is working.

## 6. Bilingual dictionary strategy and representative examples

Create `web/src/lib/search/concepts.data.json` with **50–100 approved concepts**, targeting about 75 across all five disciplines (roughly 10–20 per discipline, with cross-disciplinary entries counted once). IDs are stable, aliases express equivalence only, `relatedIds` are documentation only. Use corpus lab keywords, timeline labels, paper titles and topics to select entries; frequency is a discovery aid, not a relevance judgment.

Seed candidates grounded in observed source vocabulary include:

| Discipline | Proposed concept examples / alias candidates |
|---|---|
| Life | protein structure / 단백질 구조; RNA splicing / RNA 스플라이싱; autophagy / 자가포식; epigenetics / 후성유전학; immunology / 면역학 |
| Chemistry | photocatalysis / 광촉매; electrocatalysis / 전기촉매; metal-organic framework / 금속 유기 골격체; asymmetric synthesis / 비대칭 합성; all-solid-state battery / 전고체 전지 |
| Physics | quantum computing / 양자 컴퓨팅; graphene / 그래핀; superconductivity / 초전도; spintronics / 스핀트로닉스; topological materials / 위상 물질 |
| Mathematics | partial differential equation / 편미분방정식; algebraic topology / 대수적 위상수학; graph theory / 그래프 이론; stochastic process / 확률 과정; number theory / 정수론 |
| Computer science | machine learning / 머신러닝 / 기계학습 / 기계 학습; deep learning / 딥러닝; graph neural network / 그래프 신경망; software testing / 소프트웨어 테스팅; parallel computing / 병렬 컴퓨팅 |

These are **review candidates**, not approved mappings or claims about a lab's actual research. Add plural/scientific spelling variants explicitly after review. `machine_learning`, `deep_learning`, `neural_network`, and `graph_neural_network` remain separate concepts; relatedness never satisfies a missing query unit. Likewise, “battery,” “solid-state battery,” and “all-solid-state battery” are not automatically equivalent.

Abbreviations need documented policy. `RNA` can be a literal scientific token and, after review, a canonical ribonucleic-acid alias; it must not expand to every RNA-related specialty. `GNN`/`MOF` require reviewed meanings and negative examples. Ambiguous `ML`, `AI`, `PDE`, etc. expand only when an unambiguous companion concept occurs in the **same query or source record**, according to an alias guard. Otherwise retain the literal token and offer a readable clarification hint; do not infer abbreviation meaning from a broad department alone. Apply guards symmetrically in query/document recognition and evaluate them from unambiguous concepts first to avoid circular activation.

Migration policy for the existing 2,832-label dictionary:

1. Retain the committed optional `search_terms.json` and its literal translated-label fallback for residual unknown query units. Preserve existing translation/keyboard capabilities during PR 1 through a temporary adapter and baseline snapshots.
2. Extract candidate aliases offline from the existing renderings; never promote an entire compound OpenAlex label and every shortened rendering into one concept automatically.
3. Approved concepts are recognized against original records using approved aliases; there is no separate implicit source-label mapping. A full label such as “Data Mining and Machine Learning Applications” can contain two concept mentions; it is not an alias for either full concept by itself. Unreviewed renderings do not add canonical concept postings.
4. Once a query span is an approved concept, match it through canonical postings only. Do not also perform asymmetric legacy translation expansion for that span. This preserves equivalent-language ordering. Remaining unknown terms can still use clearly attributed legacy translation evidence at low weight.
5. Keep API generation out of the implementation workflow. Exporter changes are unnecessary for this initial concept file. A missing optional legacy dictionary must still leave literal search and bundled approved concepts working; communicate reduced fallback coverage if applicable.

Review each entry for Korean scientific usage, actual source examples, narrow-versus-broad meaning, collisions, abbreviations and negative examples. Require `review.status='approved'`, reviewer and date before runtime inclusion; draft entries are ignored. Every alias change bumps the dictionary version and runs pair-equivalence/negative tests plus the benchmark. Store review notes and uncovered high-value queries in `docs/search/dictionary-review.md`; inspect coverage after each dataset export. Communicate “등록된 한·영 연구 용어를 함께 찾습니다. 사전에 없는 표현은 입력한 글자로 찾습니다.” rather than promising arbitrary translation or semantic similarity.

## 7. File-by-file implementation checklist

Execution is recorded in [the implementation progress report](docs/search/progress.md).
Checked items have completed engineering work; the report identifies automated
verification and remaining human/device gates separately. “Verify” and “Done” below
retain the planned acceptance criteria, not a claim that every release gate has
passed. T1/T6 remain open for human relevance/terminology review, and T12/T13 for
the remaining release validation. The user requested automated phone/IME checks
only for now. Generated datasets and unrelated curation remain unchanged.

- [ ] **T1 — Freeze the benchmark and capture current behavior.** Files: new `docs/search/benchmark.json`, `docs/search/baseline.md`, `docs/search/dictionary-review.md`; inspect current `web/src/lib/search.ts`, `web/public/data/*` and Git state. Changes: first record commit/data/dictionary hashes and turn the section 9 query inventory into cases with explicit filters (T1a). After T2 supplies the harness, collect current engine IDs/order/reasons for all cases and review pooled candidate relevance with original sources (T1b). Keep unreviewed labels null. Dependencies: T1a has none; T1b needs T2 and must finish before T3 changes the engine. Verify: fixture IDs and paper associations exist; include all five disciplines, bilingual pairs, old keyboard correction and known boundary failures; review evidence independently of old score order. **Done:** a reproducible current-engine baseline and a review-status-aware benchmark are recorded as implementation artifacts; no unreviewed case is counted as a passed relevance test.

- [x] **T2 — Add the smallest test harness.** Files: `web/package.json`, lockfile, new `web/vitest.config.ts`, `web/vitest.benchmark.config.ts`, `web/tests/search/*`, `web/scripts/search-check.mjs`, and `.github/workflows/deploy.yml`. Changes: add one compatible pinned Vitest dev dependency for pure TypeScript tests; use the already declared `playwright-core` dependency with `node:assert/strict` for browser interactions. Explicitly configure test inclusion and Node environment; do not add a React DOM test stack unless a concrete gap requires it. Add scripts listed in section 9; run pure search tests before build in CI. Keep browser checks explicit/local initially, with configured installed browser channel. Dependencies: T1a inventory only; this task enables T1b capture. Verify: a deliberately failing fixture fails the process, and the real baseline tests run through the new commands; typecheck/build remain separate. **Done:** deterministic offline unit tests plus an assertion-based browser entry point work without runtime services or a new browser download requirement.

- [x] **T3 — Refactor the cached engine and preserve provenance.** Files: old `web/src/lib/search.ts`, new search directory `types.ts`, `normalize.ts`, `keyboard.ts`, `index.ts`, `query.ts`, `rank.ts`, `concepts.ts`; `web/src/data/DataContext.tsx`. Changes: establish section 4 contracts, preserve `fromKeyboard`, move normalization to index time, keep all original fields/IDs, build record/posting maps once, and retain existing translated-label fallback via an adapter. Keep the dictionary interface empty/compatible until T6. Remove the old module after imports resolve to the directory. Dependencies: T2 and T1b current-engine capture. Verify: unit fixtures for records, null fields, per-paper associations, shared papers, keyword timeline provenance, no mutation of input data, one index instance across route/filter/query changes, new index on new dataset. **Done:** React-free engine and stable per-Atlas cache are in place; no lost paper IDs or concatenated title records; existing search features have characterization coverage.

- [x] **T4 — Implement filters, literal coverage, name priority and deterministic ranking.** Files/functions: `query.ts:passesSearchFilters/filterLabIds/collectLabMatch/searchLabs`, `rank.ts:rankLabMatch/compareResults`, `normalize.ts`; remove or re-export `data/explore.tsx:passesFilters` from the shared helper. Changes: all-term policy, punctuation/empty handling, complete Latin boundaries, scoped Korean rules, exact names, coherent-versus-scattered tiers, bounded contributions, quality cautions and stable IDs; filter-aware keyboard fallback. Dependencies: T3. Verify: exact names, boundary negatives, multi-record adversarial fixtures, filtered top-N, repeated-paper caps, stable order under shuffled input arrays, empty/punctuation cases and correction precedence. **Done:** one documented deterministic matching/ranking policy produces complete filtered responses and never relies on publication counts for relevance.

- [x] **T5 — Connect all current search surfaces to one response.** Files: new `data/useLabSearch.ts`; `ExplorePage.tsx`, `Toolbar.tsx`, `SearchBox.tsx`, `ListView.tsx`, `ShortlistPage.tsx`, and search-related types in `explore.tsx`. Changes: explorer computes once; Toolbar passes ranked suggestions and counts; SearchBox becomes a renderer with callbacks and no engine/Atlas lookup; graph gets filtered matched IDs; list receives rank order and a controlled relevance/explicit-sort mode; shortlist uses the same hook, dropping its redundant `useSearch` wrapper. Preserve the existing 8/12 presentation limits until T10. Dependencies: T4. Verify: one fixture response produces identical candidate membership across graph/list/suggestions/shortlist with identical filters; relevance survives ListView; counts distinguish graph labs from hits; explicit numeric sorts work. **Done:** no independent matching/filtering/ranking logic remains in components, and suggestion picks cannot target a filtered-out node.

- [ ] **T6 — Review 50–100 concepts from the actual corpus.** Files: new `concepts.data.json`, `docs/search/dictionary-review.md`, benchmark judgments; read `pipeline/curation/search_terms_ko.json` and exported terms without regenerating them. Changes: follow section 6; record actual lab/paper examples, review metadata, alias boundary modes, collisions, guard context, language variants and separate related concepts. Dependencies: T1; can proceed alongside T3–T5. Verify: every approved ID is unique, every alias is nonempty, source evidence exists, equal aliases do not collide without an explicit policy, all five disciplines are represented, compound topics are not collapsed. **Done:** 50–100 approved entries with provenance and reviewer/date; draft-only entries never affect production retrieval.

- [x] **T7 — Implement canonical concepts and phrase semantics.** Files/functions: `concepts.ts:compileConcepts`, `normalize.ts`, `index.ts`, `query.ts:interpretQuery/collectLabMatch`, `rank.ts`; unit tests and benchmark evaluator. Changes: longest-phrase recognition in both documents and query, reviewed Korean spacing, abbreviation guards, quoted unknown phrases, mixed-language residuals and canonical score keys; isolate legacy fallback as specified. Dependencies: T4, T6. Verify: bilingual concept-only IDs/scores/order exactly equal under identical filters; longest matches, plural aliases, unknown tokens, abbreviation ambiguity, GNN scattered negative and ML/deep-learning distinction. **Done:** all concept invariants pass and reviewed benchmark differences have evidence-based dispositions.

- [x] **T8 — Render truthful explanations and safe emphasis.** Files: new `web/src/components/SearchEvidence.tsx`; SearchBox, ListView, ShortlistPage, optional LabPanel search-evidence prop; `web/src/styles.css`; Korean copy in `AboutPage.tsx`. Changes: consistent field labels, best original record, expandable coverage evidence, concept badges, valid paper links and cautions; explain keyboard correction and scattered coverage. No fabricated original offsets. Dependencies: T5, T7. Verify: every displayed explanation traces to a record/paper; all required units can be inspected; Korean/English aliases do not claim absent literal text; HTML-like input renders as text; name matches for flagged labs stay visible. **Done:** users can see why each result qualified and whether associations are questionable, with no misleading highlighting.

- [x] **T9 — Fix IME, keyboard selection and accessibility.** Files: SearchBox, shared search-input behavior if extracted, shortlist SearchSection, styles, browser checks. Changes: composition tracking/guards, active-ID selection reset/clamp, Escape/Arrow/Enter behavior, mounted listbox/option references, visible full-results action, status messages and focus styles; follow section 8. Dependencies: T5, T8. Verify: synthetic composition/keydown sequences and actual Korean IME manually; zero/changing results, mouse/keyboard focus, accessible names/states, light/dark/mobile. **Done:** composition never navigates/selects, no invalid selection or dangling active descendant, and keyboard users can reach results and controls.

- [x] **T10 — Make all results reachable.** Files: Toolbar/SearchBox full-results callback, ExplorePage, ShortlistPage SearchSection, ListView, styles. Changes: dropdown footer “전체 N개 결과 보기” opens filtered relevance list; shortlist starts at 12 and adds 12 per “더 보기”; reset visible limit on query/filter identity changes. Keep all engine results. Explorer can retain its complete table initially; add pagination only if measurement calls for it. Dependencies: T5, T8, T9. Verify: fixtures with 0/1/8/9/12/13/many results; repeatedly load more until union equals response IDs exactly once; focus retained and newly revealed content announced; last button disappears. **Done:** no matching lab is trapped beyond a fixed truncation and explicit list sorting affects the full set before slicing.

- [x] **T11 — Persist validated query/filter state in hash-route URLs.** Files: new `web/src/data/searchUrl.ts`; `explore.tsx`, ExplorePage, ShortlistPage, Header/navigation in App, LabPage return links as necessary; URL unit/browser tests. Changes: section 8 codec and history rules, route-specific search state, canonical filter order, explicit sort/view/edge mode, preserve `labs`/`dummy`/unrelated parameters, replace shortlist `setParams({})` with deletion of only `labs`, and retain explorer state on detail/shortlist visits. Dependencies: T5, T9, T10. Verify: initial direct load, reload, Back/Forward, editing then submitting, detail return, malformed parameters, unavailable clusters, shared shortlist import/return, URLs under a Pages subpath. **Done:** URL is authoritative on route entry/history navigation, provider snapshots do not overwrite restored state, and shared shortlist IDs/local storage retain existing semantics.

- [ ] **T12 — Measure performance and apply only demonstrated fixes.** Files: new `web/scripts/search-perf.mjs` or a browser measurement mode of `search-check.mjs`, unit benchmark entry point, `docs/search/performance.md`; engine/hook/cache files only as evidence requires. Changes: measure section 10 cold index, warm queries, render delay and heap; count builds; address redundant work first; add debounce/worker only on measured need with stale-response tests. Dependencies: T7–T11. Verify: real dataset, representative phone, desktop, high-match and zero-match queries, repeated typing and navigation; document raw observations and device conditions. **Done:** a reproducible report exists, sub-100 ms post-index query target is evaluated honestly, and any optimization preserves all functional invariants.

- [ ] **T13 — Finish release verification and documentation.** Files: README, AboutPage copy, `docs/search/{baseline,dictionary-review,performance}.md`, workflow and tests as needed. Changes: describe supported languages/coverage, keyboard correction, all-term policy and limitations; run required section 9 checks; audit imports for old search logic. Dependencies: T1–T12. Verify: unit tests, reviewed benchmark, browser checks, manual IME/accessibility, typecheck/build and existing graph/shortlist regression smoke checks. **Done:** all required acceptance items have recorded outcomes, pending relevance reviews are resolved, no unrelated dataset/recommendation changes, and all three PRs together satisfy this plan.

## 8. UI behavior, accessibility, URL state, and Korean copy

### 8.1 Search, sorting and result access

SearchBox takes `query`, supplied ranked rows, total/counts, `onQuery`, `onPick`, and `onViewAll`; it does not import matching code. Each row includes lab identity, affiliation and concise evidence. A footer button outside the listbox provides “전체 N개 결과 보기”; do not place a separately interactive button inside an option. An ordinary committed Enter with no active option opens full results; Enter with a valid active option selects that lab, preserving explorer graph focus/list navigation behavior. No-results Enter does nothing except retain the input/status.

Store selection as lab ID or `null`, not a numeric index assumed valid forever. For ArrowDown with no selection, select the first result; ArrowUp may select the last. With zero rows, both are safe no-ops. Clamp/reset when query, filters, results, route or correction changes. Preserve active ID only when it remains in the current suggestion array. Escape closes suggestions and clears active selection; handle propagation so it does not unexpectedly clear a graph selection while dismissing the dropdown. Tab follows normal focus order.

Use `onCompositionStart`/`onCompositionEnd` plus `nativeEvent.isComposing`; guard Enter (and selection navigation) during composition. Include the browser compatibility `keyCode===229` fallback only as an explicit documented guard, with a fixture. Keep draft input responsive; run search and URL commit on completed composition, not intermediate Hangul assembly. The composition-ending Enter must not also select a suggestion. Browser automation cannot replace a manual Windows Korean IME and available mobile Korean keyboard check.

Retain accessible combobox input label, `aria-expanded`, `aria-autocomplete=list`, `aria-controls`, listbox/options, and valid `aria-selected`/`aria-activedescendant` only for a mounted active option. Use stable IDs from lab IDs plus component ID. Announce result counts/no-result status politely after committed changes, not every intermediate composition event. Keep focus on input during list navigation, visible focus on footer/load-more/sort actions, and sensible pointer/touch behavior without relying on a blur timeout for correctness.

List sorting becomes controlled state. When starting a new nonempty query, use relevance unless an explicit sort is restored from that URL. Changing the query resets an old manual sort to relevance; filter-only changes preserve the user's current explicit sort. A visible “관련도순” control restores engine ordering. Clearing search returns to browse default (papers descending). Explicit name/university/field/cluster/paper/senior sorts retain deterministic ID ties and operate on all results before pagination. Relevance never gets overwritten merely by mounting ListView or switching graph/list mode.

Graph keeps all labs passing filters and existing edge/layout/selection logic. With a query, toolbar says `지도 N곳 · 검색 일치 M곳`; counts refer to filtered graph membership and matched IDs, not the count of prominent labels at current zoom. If the graph already prioritizes a selected node/edge, keep that priority. During empty search supply `matched=null`; during a nonempty zero-result query supply an empty set. Clear a pinned preview only when the selected lab is filtered out, not merely because it fails the text query.

The shortlist's interest search uses all labs by default, independent of saved candidates and recommendation field controls. Explicit URL search filters must be displayed as removable chips if present; they cannot be hidden. Do not merge search sorting into the vector-based recommendation or comparison code. Initial 12 results expand by 12, with total and shown counts, stable focus and no duplicates.

### 8.2 URL codec and history rules

Use React Router's hash-route search parameters, e.g. `#/` followed by `?q=...&univ=kaist,snu&field=cs&cluster=3&view=list&sort=relevance&edge=similarity`. These are parameters **inside the hash**, not `window.location.search`. On shortlist use the same search keys alongside `#/shortlist?labs=...`; recommendation controls retain their existing independent behavior. An original-input retry sets `correction=off`, passes `keyboardCorrection:false` through the hook, and re-runs the same raw query without fallback. A newly edited query restores correction by default; URL restoration honors an explicit `off` state. The action must not immediately trigger the same automatic correction again.

Proposed codec signatures in `searchUrl.ts`:

```ts
type SearchSort = 'relevance' | 'name-asc' | 'name-desc' | 'univ-asc' | 'univ-desc'
  | 'field-asc' | 'field-desc' | 'cluster-asc' | 'cluster-desc'
  | 'papers-asc' | 'papers-desc' | 'senior-asc' | 'senior-desc';
interface SearchUrlState {
  query: string;
  filters: SearchFilters;
  datasetVersion: string;
  keyboardCorrection: boolean;
  view: 'graph' | 'list';
  edgeMode: 'similarity' | 'coauthor' | 'cross';
  sort: SearchSort;
}
function parseSearchParams(params: URLSearchParams, validClusterIds: ReadonlySet<number>,
  currentDatasetVersion: string): {
    state: SearchUrlState;
    filterState: 'valid' | 'invalid' | 'stale';
    notices: readonly string[];
  };
function writeSearchParams(previous: URLSearchParams, state: SearchUrlState): URLSearchParams;
```

Validate university/discipline enums, numeric cluster membership, sort/view/edge/correction choices and query limits. Deduplicate and deterministically order multi-value parameters; omit defaults. Preserve unrelated keys by cloning params and modifying only owned keys. Treat an explicit set whose every value is invalid as `filterState='invalid'` with a visible notice and a user action to reset; do not silently broaden a shared filtered search to all labs. A mix of valid/invalid values retains valid selections and reports ignored values. The adapter blocks invalid searches until the user clears the invalid set. Attach `datasetVersion` to shared filtered links as `data`; compare it with `currentDatasetVersion` on parse. Old/deleted cluster IDs may change meaning between exports: a version mismatch with active cluster filters yields `stale` and a notice/action to clear or explicitly accept the current cluster interpretation. A missing version on a legacy link may use current valid IDs with a notice. Do not assert identical historical cluster membership.

Use the URL as source of truth on initial route entry and every POP/Back/Forward navigation. Keep immediate draft input local for IME. On the first committed edit of a search interaction, push one history entry containing the prior-to-new transition; replace that entry for subsequent keystrokes in the same interaction. End the interaction on Enter, suggestion/full-results action, blur or filter/view change. Filter toggles, explicit sort changes and view changes push navigable states. Do not push an entry per character. Reconcile URL changes to draft/provider state with equality checks; do not use two unconditional effects that keep overwriting each other. Cancel pending draft/URL updates on POP or route changes.

Preserve the explorer provider's latest canonical URL for in-app return links from details/shortlist. A literal fresh `#/` means default browse state; a link labeled return-to-explorer may explicitly use the saved URL. Back must restore the actual historical URL, not a newer provider snapshot. On shortlist, share-copy should serialize the current search keys plus displayed `labs` when sharing that view; importing/returning to the private shortlist deletes only `labs`. Search restoration must never overwrite local shortlist storage or change recommendation seeds except through existing explicit actions.

### 8.3 Proposed Korean copy

| Context | Copy |
|---|---|
| Input label / placeholder | `교수·연구실 이름 또는 연구 주제 검색` / `예: 기계학습, 단백질 구조, graph neural network` |
| Coverage explanation | `등록된 한·영 연구 용어를 함께 찾습니다. 사전에 없는 표현은 입력한 글자로 찾습니다.` |
| Query policy | `입력한 주제가 모두 포함된 연구실을 찾습니다. 여러 논문에 나뉘어 나타난 결과는 뒤에 표시합니다.` |
| All results | `전체 37개 결과 보기` (actual count) |
| Shortlist pagination | `37곳 중 12곳 표시` / `12곳 더 보기` (remaining-aware count) |
| No matches | `일치하는 연구실이 없습니다. 다른 표현이나 이름으로 검색해 보세요.` |
| Filter restriction | `선택한 필터에서는 결과가 없습니다.` + `필터 해제` and, only if computed, `전체에서는 N곳이 일치합니다.` |
| Invalid punctuation | `이름이나 연구 주제를 입력해 주세요.` |
| Concept evidence | `키워드에서 찾음 · 기계학습 ↔ Machine Learning` with actual original label |
| Scattered evidence | `여러 항목에서 함께 찾음` with expandable per-unit records |
| Paper caution | `동명이인의 논문이 섞였을 수 있어 이 근거는 확인이 필요합니다.` |
| Wrong-field caution | `연구자와 논문의 연결이 정확한지 확인이 필요합니다.` |
| Keyboard correction | `‘aus dur’을 ‘면역’으로 바꿔 찾았습니다.` with a clear way to retain/retry the original input |
| Ambiguous abbreviation | `‘ML’은 여러 뜻이 있어 입력한 글자로 찾았습니다. 연구 주제를 함께 입력해 보세요.` |
| Relevance label | `관련도순` and an explanation that it is query fit, not lab evaluation |

Adjust these examples to approved dictionary policy and actual engine output; never display a bilingual/correction/evidence claim that did not occur. Update stale copy in ShortlistPage and AboutPage together with engine behavior.

## 9. Benchmark, test coverage, and acceptance criteria

### 9.1 Proposed 50-case review inventory

This is a starting inventory to review, not measured accuracy. Each row is one case; pair IDs allow equal-language checks. `all` means all filter sets empty. Resolve the example math cluster from the current fixture lab when freezing the benchmark, then store its numeric ID and dataset fingerprint explicitly.

| ID | Query | Filters / purpose |
|---|---|---|
| 01 | `machine learning` | all; pair ML |
| 02 | `기계학습` | all; pair ML |
| 03 | `기계 학습` | all; Korean spacing |
| 04 | `머신러닝` | all; alias |
| 05 | `deep learning` | all; pair DL; distinct from ML |
| 06 | `딥러닝` | all; pair DL |
| 07 | `graph neural network` | all; pair GNN |
| 08 | `그래프 신경망` | all; pair GNN |
| 09 | `protein structure` | all; pair protein |
| 10 | `단백질 구조` | all; pair protein |
| 11 | `RNA splicing` | all; pair splicing |
| 12 | `RNA 스플라이싱` | all; mixed script, pair splicing |
| 13 | `photocatalysis` | all; pair photo |
| 14 | `광촉매` | all; pair photo |
| 15 | `all-solid-state battery` | all; pair battery; reviewed plural variants |
| 16 | `전고체 전지` | all; pair battery |
| 17 | `quantum computing` | all; pair quantum |
| 18 | `양자 컴퓨팅` | all; pair quantum |
| 19 | `graph theory` | all; pair graph theory; separate from GNN |
| 20 | `그래프 이론` | all; pair graph theory |
| 21 | `partial differential equation` | all; pair PDE |
| 22 | `편미분방정식` | all; pair PDE |
| 23 | `algebraic topology` | all; pair topology |
| 24 | `대수적 위상수학` | all; pair topology |
| 25 | `software testing` | all; pair software |
| 26 | `소프트웨어 테스팅` | all; pair software |
| 27 | `immunology` | all; pair immune; existing translation behavior |
| 28 | `면역학` | all; pair immune |
| 29 | `이병훈` | all; exact Korean PI |
| 30 | `Byung-Hoon Lee` | all; exact English PI |
| 31 | `성민혁` | all; exact Korean PI |
| 32 | `Minhyuk Sung` | all; exact English PI |
| 33 | `KAIST Visual AI Group` | all; exact stored lab name |
| 34 | `단백질 구조 deep learning` | all; two concepts, mixed language |
| 35 | `graphene 광촉매` | all; mixed language/disciplines |
| 36 | `RNA` | all; scientific boundary negative |
| 37 | `GNN` | all; abbreviation policy |
| 38 | `ML` | all; ambiguous abbreviation remains literal unless guarded |
| 39 | `AI` | all; ambiguous abbreviation |
| 40 | `FoldMason` | all; corpus literal outside initial concept vocabulary |
| 41 | `"graph neural network"` | all; explicit phrase |
| 42 | `machine learning` | univ kaist AND field cs |
| 43 | `기계학습` | same filters as 42; filtered bilingual equivalence |
| 44 | `편미분방정식` | field math AND frozen cluster of `hanyang-A5000509319` |
| 45 | empty string | univ yonsei; browse semantics |
| 46 | spaces only | all; browse semantics |
| 47 | `zxqvnomatch913` | all; intended zero, verify on frozen dataset |
| 48 | `aus dur` | all; existing keyboard-layout correction |
| 49 | `이병훈` | univ kaist; intended filter-restricted name result |
| 50 | `,` | all; invalid normalized-input regression |

Verified exact-field fixtures: rows 29/30 uniquely identify `dgist-A5000829476`; rows 31/32/33 identify `kaist-A5004099860`. Additional unique-name fixtures available for tests: `박진주` / `Chin-Ju Park` → `gist-A5004486606`, and `김승혁` / `Seunghyeok Kim` → `hanyang-A5000509319`. These are verified dataset identity matches; they do not establish broad topic relevance.

Candidate topic evidence to review (present in checked-in records, **not judged relevant here**):

| Topic | Source evidence |
|---|---|
| GNN | `W4388636776`, “MolNet_Equi: A Chemically Intuitive, Rotation‐Equivariant Graph Neural Network”; association `kaist-A5030760350` |
| Machine learning | `W4409094515`, “Self-supervised machine learning framework for high-throughput electron microscopy”; `snu-A5079762603` |
| Protein structure | `W7126115639`, “Multiple protein structure alignment at scale with FoldMason”; `snu-A5019985343` |
| All-solid-state batteries | `W4385467910`, “All-solid-state lithium–sulfur batteries enabled by single-ion conducting binary nanoparticle electrolytes”; `postech-A5042482017` |
| Quantum computing | `W4285726263`, “All-Photonic Architecture for Scalable Quantum Computing with Greenberger-Horne-Zeilinger States”; `snu-A5036452401` |
| PDE | `hanyang-A5000509319` keyword “Nonlinear Partial Differential Equations”; inspect its introduction too |
| Photocatalysis | `W4388938997`, “Ultrathin covalent organic overlayers on metal nanocrystals for highly selective plasmonic photocatalysis”; `postech-A5046753852`, `gist-A5038852259` |
| RNA | `W4207031823`, “Single‐cell RNA‐sequencing of Nicotiana attenuata corolla cells reveals the biosynthetic pathway of a floral scent”; `kaist-A5102961870` |

Synthetic obvious negatives supplement real judgments: a lab whose only title is “Internal transport” must not match RNA; three different papers containing graph/neural/network must not satisfy the GNN concept; deep-learning-only evidence must not satisfy machine learning via a synonym collapse; an out-of-filter exact-name lab must not occupy a suggestion slot. These are specified fixture expectations, not a claim that a real lab is irrelevant based on one title.

Benchmark format: each case stores `{id, query, filters, pairId?, purpose, judgments, reviewStatus, reviewer, reviewedAt}`; each judgment stores `{labId, grade: 0|1|2|null, evidence: [{field, paperId?, originalText}], reason}`. Null means unjudged, not irrelevant. Preserve dataset/engine/dictionary versions and capture both original and correction interpretations. Reviewer grades 2 = directly useful, 1 = broader/plausibly useful, 0 = clear false positive; data-association concerns are recorded separately.

Pool current and proposed top-10 results plus the source candidates above, then inspect evidence and obvious negatives. Sample outside the pool to assess missed known relevant IDs. Split related query families together into tuning and held-out sets before tuning weights; do not put Korean and English aliases of the same concept in different partitions. Record judged coverage@10, known-relevant recall@10, MRR for identity queries and graded nDCG@10 over sufficiently judged cases. Unjudged rows do not become zero-grade labels; do not report full-corpus recall from this small pool.

### 9.2 Required tests and release gates

| Area | Meaningful fixture / expected behavior |
|---|---|
| Concept equality | For every approved bilingual concept with equivalent guards, same complete IDs, scores/order under all and representative filters; alias text itself cannot add score |
| Names | Unique exact stored PI/lab names rank first; duplicate exact names have deterministic ties; missing names and flagged labs do not crash/disappear |
| Phrase coherence | An unknown unquoted multiword query gets highest relevance for contiguous same-title words, then noncontiguous words in one record, then scattered coverage; an atomic reviewed GNN or quoted phrase excludes scattered word assembly entirely |
| Boundaries / normalization | RNA/internal/RNase, Unicode composed/decomposed Hangul, width/case, reviewed Korean spacing, punctuation-only, literal regex metacharacters, scientific symbols |
| Dictionary | Duplicate IDs/aliases, collisions, longest phrase, explicit plurals, ambiguous abbreviations with and without guard, related-concept non-expansion, missing optional legacy terms |
| Unknown/mixed query | All remaining terms required; known + unknown and Korean + English; no-match input stays zero without a qualifying keyboard correction |
| Ranking | Shuffle labs/papers/aliases and keep same IDs/order; repeated duplicate titles and additional paper volume cannot overcome tier precedence/caps |
| Data quality | Each flag; questionable evidence cannot promote research match; exact name remains; shared paper association valid for one lab does not validate another |
| Filters/limits | OR within/AND across facets, multi-discipline labs, selected empty cluster, eligible match after eight out-of-filter global hits; page size never affects engine membership |
| Cross-surface consistency | Same response under identical filters; suggestions equal first eight; graph matched set equals complete response set; list relevance preserves response order; shortlist uses same options |
| Accessibility/IME | Composition Enter doesn't pick or submit; ArrowDown at zero; shrinking/reordered results; stale active ID; Escape; valid ARIA references and focus; actual Korean IME manual check |
| Full results | >12 shortlist hits reachable exactly once, >8 suggestions access full list, reset on query/filter changes, sorting before slicing |
| URL | Direct-load/reload/Back/Forward; filters/query/sort; malformed and stale cluster values; subpath hash routing; `labs`/`dummy`/unrelated keys retained; no rewrite loop |
| Existing features | Graph edge/hover/pin/mobile preview, stars/local shortlist persistence, shared shortlist import, recommendation seeds/field controls and comparison remain functional |

Functional gates: all deterministic invariants above pass. All 50 benchmark cases have review status and outcomes recorded; all topic cases used for relevance metrics have sufficient reviewed labels. Target a measurable improvement over baseline on reviewed bilingual topic queries with no unreviewed regressions in exact names or filter correctness. Proposal for the first release gate: no lower aggregate held-out nDCG@10/known-relevant recall@10 than baseline, and at least one improves; investigate each newly introduced grade-0 top-3 result and resolve it or record an explicit reviewer-accepted tradeoff. Keep metrics partitioned by language/discipline and report small-sample limits. Do not adjust judgments to make scores pass. These are acceptance targets, not achieved results.

### 9.3 Commands: existing versus proposed

**Verified existing scripts/commands** (not executed for this plan). Run frontend commands from `web/` after dependencies have been installed by an implementation session:

```powershell
npm run typecheck
npm run build
npm run preview -- --port 4173
```

Keep preview running in a separate terminal. Existing graph screenshot/FPS check, also from `web/`:

```powershell
node scripts/check.mjs ../docs/screenshots/search-review
```

It requires an installed Microsoft Edge channel and a running preview server; its output is evidence to inspect, not a comprehensive passing assertion suite. Use a new output folder to avoid overwriting existing screenshots unintentionally. Existing Python commands from repo root (pipeline dependencies required):

```powershell
python -m pytest -q pipeline/tests
python -m pipeline.run --steps validate,fields --offline
```

The workflow contains both commands; the second also writes field statistics. Do not run collection, embedding, API translation or live `--stage verify` merely to validate this frontend change. Pipeline tests remain a CI requirement; locally, include them when export/schema behavior changes or before the full release gate.

**Proposed commands requiring T2/T12 configuration** (do not assume they already exist):

```powershell
# web/; proposed package script: "test": "vitest run"
npm run test
# proposed package script: "benchmark:search": "vitest run --config vitest.benchmark.config.ts"
npm run benchmark:search
# existing playwright-core + new assertion script, preview already running
node scripts/search-check.mjs
# proposed real-browser timing/heap report script, preview already running
node scripts/search-perf.mjs
```

Configure the normal runner to exclude `tests/search/benchmark/**`; the separate benchmark config includes only that directory, uses the Node environment, and writes review-aware metrics/artifacts to an explicit output path. Timing must not make ordinary tests flaky. Choose a Vitest version compatible with this repository's actual Node 20/Vite 5 toolchain during implementation and pin it in the lockfile; verify package engine/peer requirements before installing. `npm ci` is already the CI dependency installation step, but was not run during planning. No browser tool/framework additions beyond existing Playwright are required unless testing evidence demonstrates a gap.

## 10. Performance and data-loading considerations

The current eager payload is approximately **32.85 MB uncompressed**, dominated by **27.69 MB of papers**. The new index may add memory even if normalization reduces repeated query work. Avoid duplicating whole Paper objects and title strings per associated lab; reference shared records and existing original strings. Keep index construction lazy and at most once per live Atlas instance, including route changes and StrictMode behavior; measure how many actual loaded instances are created rather than claiming one process-wide build.

Measurement procedure for T12:

1. Record commit, dataset hashes/counts, dictionary version, browser/OS/device, cache state and power/network conditions. Use a production build. Include an actual representative phone with its model recorded; desktop CPU throttling is supplemental evidence only.
2. Measure fetch/parse/Atlas creation separately from cold index construction and first query. Use `performance.mark/measure`; report duration and main-thread long tasks. Do not hide index time inside “query latency.”
3. Warm the index, then run the fixed benchmark and incremental typing sequences repeatedly (proposal: 5 warmups and 30 measured runs per case). Report p50/p95/max post-index engine latency and input-to-visible-results delay for frequent, mixed-language, corrected, filtered and zero-match queries.
4. Measure heap before/after index construction and after repeated query/route cycles where supported; report allocation/string/record counts as portable supplemental metrics. Do not present JSON bytes or a serialized index size as browser heap. Record total fetched/encoded/decoded resource sizes from browser tooling rather than equating disk size with transfer.
5. Use real current data. Existing `?dummy=300` graph fixtures have no papers and cannot establish realistic search indexing/memory performance. A larger synthetic search fixture must include distinct paper titles/topics and be labeled synthetic.

Initial target: **p95 post-index engine query time below 100 ms on the representative phone**, with input remaining responsive. This is a target to validate, not a benchmark result. Record cold indexing separately and agree on a cold-start budget from actual measurements. Do not introduce debounce by default: pre-normalization, stable index lifetime and one explorer query computation come first. If typing still causes repeated blocking work, measure a small deferred/debounced committed-query strategy; keep the input responsive, flush on submit/composition end, and ensure all views/counters use the same committed query. A worker is justified only if measured indexing/query work blocks interaction; tag messages with dataset/query IDs and discard stale responses. Neither optimization may mix old suggestions with new graph/list states.

**Adding a compact search index does not reduce initial downloads while DataProvider still eagerly fetches the full `papers.json`.** It would add another file and may duplicate memory. The initial required release retains current loading and documents its cost. Plan compact indexing and lazy detail loading together in the separate future phase, including every current paper consumer.

## 11. Risks, assumptions, and practical mitigations

| Risk or nonblocking assumption | Mitigation / decision |
|---|---|
| Checkout changed substantially during planning | This plan is rebased on `8d4d049`; recheck HEAD/diff and hashes before implementation. Preserve existing F1 translations and keyboard correction deliberately. |
| Existing model-generated translations are broad or ambiguous | Treat them as reviewed-concept candidates and lower-weight literal fallback; never claim all 2,832 entries are approved synonyms. |
| 50–100 concepts cannot cover all disciplines fully | Sample each discipline; publish supported-coverage wording; track uncovered queries; preserve literal/legacy fallback. |
| Human relevance/alias review has not happened for this plan | Fill reviewer/date/judgment fields in T1/T6. Implementation can start with synthetic invariants and draft entries; final relevance acceptance and approved dictionary require review. |
| Medium author confidence is common | 761/852 labs are medium. Do not blanket downrank/exclude names; evaluate actual exposed association flags. |
| Lab-level quality flags cannot identify each wrong title | Caution and cap dependent research evidence; preserve identities; do not invent per-paper flags. Private review notes remain a documented limitation. |
| Boundary rules can reduce recall of inflections/compounds | Add reviewed plural/scientific aliases and corpus tests; defer general stemming/typo tolerance until measured. |
| Exact lab names contain English aliases such as AI | Full stored-name equality has priority over topic interpretation; only actual name fields qualify. |
| Korean whitespace and particles are difficult | Scoped reviewed alias segments and literal fallback first; do not promise arbitrary morphology. |
| Cluster IDs may be regenerated on data export | Validate against current data, carry dataset version on shared filters and warn/reset explicitly on stale/invalid filters. |
| URL/provider feedback loops or IME updates create stale results | One canonical committed state, route-navigation reconciliation, canceled pending edits and targeted browser tests. |
| Increasing dictionary/index size affects mobile responsiveness | Measure real data/phone; avoid duplicate records, use stable cache; add worker/debounce only with evidence. |
| Installed browser availability varies | Existing checks use Edge; make new script browser channel configurable and document prerequisite. Do not claim manual IME was automated. |
| The user requests a plan only | This document is the deliverable. Installation, application changes, test execution, commits and pushes belong to a separately authorized implementation session. |

There is **no blocking unknown for delivering this plan**. The future release needs reviewed relevance/alias judgments and access to a representative phone for the stated performance claim; these are explicit verification dependencies, not reasons to stop the planning task. Default UI decisions are as specified here (all labs on shortlist, relevance on a new query, incremental shortlist results, existing complete explorer table).

## 12. Three ordered PRs

### PR 1 — Shared engine, baseline tests, consistent integration/filtering/ranking

Tasks: T1–T5, with draft concept review T6 allowed in parallel. Begin with a baseline of **the current shared engine**, not the removed `matchesQuery` implementation. Refactor record/index contracts and normalization; keep existing translation/keyboard behavior through explicit adapters, introduce deterministic relevance and quality policy, and make filters/results/sort ownership consistent. Put literal/name/filter/ranking tests and cross-surface assertions in place. The future concept compiler interface can initially be empty; do not advertise approved bilingual parity before PR 2.

Exit gate: new pure tests plus typecheck/build pass; baseline artifacts reviewed/status-labeled; suggestions respect filters before eight-item truncation; list defaults to relevance during search; graph matched IDs agree; shortlist uses the same engine; names/keyboard behavior and recommendations have no unexplained regressions. Fixed 8/12 presentation limits and unfinished URL/IME work are explicitly pending PR 3, not a completed release.

### PR 2 — Bilingual concepts, phrase handling, evidence

Tasks: finish T6, then T7–T8. Add 50–100 reviewed concepts, symmetric query/document recognition, explicit phrase boundaries, conservative abbreviation rules and original-record evidence. Retain legacy translated-label fallback as a separate method. Evaluate the frozen benchmark and inspect relevance changes by language/discipline; tune weights only on the tuning partition.

Exit gate: approved concept-only bilingual query pairs have identical IDs/scores/order; exact names rank first; coherent/scattered adversarial tests pass; related concepts stay distinct; every shown reason has original evidence and valid IDs; quality cautions are tested. Reviewed held-out metrics meet the provisional acceptance gate or concrete changes are made before merging.

### PR 3 — IME/accessibility, full results, URL state, measured performance fixes

Tasks: T9–T13. Finish safe Korean input and combobox behavior, access beyond every result limit, authoritative URL state/history, and performance measurement. Fix measured costs without changing retrieval semantics. Update Korean copy, README/methodology, and final release verification records.

Exit gate: required unit/browser checks and manual Korean IME checks pass, full-result reachability/URL restoration are demonstrated, graph/shortlist regressions pass, and actual phone performance is reported against the target. A failure to achieve the target is reported and addressed or explicitly scoped with a reviewed limitation; no unmeasured latency claim. All required release tasks must be complete before calling the feature finished.

## 13. Optional future work — outside the required release

- [ ] **F1 — Compact exported index with versioned manifest.** Files: `pipeline/step10_export.py`, new export helper, `pipeline/schemas.py`, `pipeline/validate.py`, corresponding web types/index loader and pipeline tests. Change: export normalized postings/record IDs and minimum original evidence, dictionary/schema/data versions and checksums; avoid publishing private abstracts/TLDR. Dependencies: T12 proves an index benefit and the engine/evidence schema is stable. Verify: exported versus in-browser-built IDs/order/evidence equivalence on the frozen benchmark, checksum/version mismatch fallback and payload/heap measurement. **Done:** reproducible compatible compact artifact with proven benefit; no claim of reduced startup downloads before F2.

- [ ] **F2 — Lazy paper details and required-data partitioning.** Files: DataContext, LabPage, LabPanel/edge evidence, Shortlist recommendations/Compare, BridgePage/topic-profile consumers, exporter and schema/loader tests. Change: pair F1 with minimum search/topic-profile metadata and per-lab or sharded paper-detail fetches; audit all `atlas.papers` / `paperById` consumers, loading/error states and shared-paper deduplication. Dependencies: F1 and a complete consumer inventory. Verify: graph/search initial network excludes full `papers.json`, evidence links resolve on demand, recommendations/bridge/shared comparisons remain correct, version mixing cannot occur, total download/heap/latency improves on real devices. **Done:** measured initial-download reduction without lost search coverage or broken paper consumers.

- [ ] **F3 — Optional semantic retrieval experiment.** Files: isolated offline evaluation/export experiment and future search adapter, only after a separate decision. Change: test whether semantic retrieval improves judged queries missed by exact/bilingual matching, with explanations and literal/name priority retained. Dependencies: reviewed benchmark and a demonstrated retrieval gap. Existing `pipeline/step07_embed.py` embeds paper title/abstract with SPECTER and builds citation-weighted normalized lab vectors; `recommend.ts` compares compatible lab vectors. **Multilingual query embeddings cannot be compared directly with existing SPECTER vectors unless their embedding spaces and query/document encoding schemes are compatible.** Re-embed both sides with a suitable common model or validate an explicitly trained alignment; matching vector dimensions is insufficient. Verify: held-out bilingual relevance, false positives, payload/latency/cost and compatible-space tests. **Done:** documented evidence of improvement and a separately approved deployment approach; no vector database, hosted service or backend without demonstrated need.

- [ ] **F4 — Broader typo tolerance or precise normalized highlighting.** Files: normalize/query/evidence modules and targeted tests. Change: evaluate errors observed in the benchmark/query feedback; add narrowly justified corrections or normalization-to-original offsets. Dependencies: exact/concept release accepted and real error cases documented. Verify: recall improvement without losing RNA/scientific/name precision, no incorrect original-text highlights, and equal-language invariants retained. **Done:** measured benefit and bounded behavior; general fuzzy matching is not silently added to the required release.

---

## Historical appendix — original planning document, preserved

The following is the pre-existing design/history. Its six-university scope, dates, counts, commands and historical claims are not the current search plan or newly verified results. Follow sections 1–13 above for the required search release, and current code/configuration for commands. The original content is retained for existing references and context.

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
