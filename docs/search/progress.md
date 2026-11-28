# Search implementation progress — 2026-11-23

Base: `8d4d0496efbde3a5c222bec5bf5a59f97059e024`.
Delivery branch: `feat/shared-bilingual-search`.
The unrelated `docs/openalex-first-design.md` and public datasets are preserved.

| Plan task | Engineering status / verification |
|---|---|
| T1 baseline | 50-case inventory and original-engine output captured with hashes. Five exact identities verified. Human topic relevance judgments remain pending. |
| T2 harness | Pinned Vitest 2.1.9 installed; unit/benchmark scripts, browser assertions and CI test step added. Existing Playwright and installed Edge reused. |
| T3 cached index | React-free modules preserve field boundaries, original text, paper IDs and association quality. One cached index per Atlas load; unit-tested. |
| T4 ranking/filtering | All-unit coverage, coherent phrases, name priority, stable ID ties, capped paper contributions, filter-aware correction and quality cautions implemented/tested. Mixed-query keyboard correction preserves known concepts/abbreviations and prefers as-typed matches. |
| T5 integration | Explorer suggestions/graph/list derive from one response; shortlist uses the same hook. Browser checks verify IDs/order, active filters and relevance sorting. |
| T6 dictionary | 64 concepts have actual corpus source examples and explicit agent-review metadata. Human terminology review remains pending. |
| T7 concepts/phrases | 128 real-corpus bilingual ID/score parity checks pass (64 concepts × all/KAIST filters). Unknown/mixed/quoted/spacing/related-concept rules have tests. |
| T8 evidence | Original records, source labels for translated matches, concept badges, per-paper links, complete unit coverage and quality cautions are displayed. No fabricated offsets/highlights. |
| T9 input/accessibility | Composition guards, safe active IDs, keyboard navigation, valid ARIA references and active-option scrolling implemented. Synthetic IME/empty/changing/mobile-viewport tests pass. Manual IME is deferred. |
| T10 complete results | Dropdown opens full list; explorer loads 50 rows at a time and shortlist loads 12. Sorting precedes slicing. Browser verifies exact complete IDs without duplicates. |
| T11 URL state | Query, filters, view, sort and correction preference restored; invalid/stale filter handling and preserved shortlist/unknown parameters tested. Query/view edits keep unresolved filters blocked until explicitly changed, cleared or accepted. Detail return and Back/Forward work. |
| T12 performance | [Desktop measurements](performance.md): worst query p95 13.3 ms; cold index 2,809.3 ms. Indexed names, reuse of matching records and paged rendering address measured costs. No per-keystroke rebuild or speculative debounce/worker. Real-phone target remains unverified. |
| T13 verification/docs | Typecheck/build, 26 unit tests, 128 real-data parity checks, 22 browser checks, and pipeline suite (61 passed, 1 skipped). Review and physical-device gates remain open. |

The user chose **automated checks only for now** for physical-phone/IME validation.
No manual device result is inferred from mobile viewport emulation. The original
plan's human relevance/terminology review gates are not claimed complete; enabled
dictionary entries transparently record Codex review. The checkbox status in the
plan marks engineering completion while the table here records those limits.

## Reproduction

From `web`, after dependencies are installed:

```powershell
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run benchmark:search
# Separate terminal:
npm.cmd run preview -- --host 127.0.0.1 --port 4173
# With preview running:
node scripts/search-check.mjs
node scripts/search-perf.mjs
```

From repository root: `.\.venv\Scripts\python.exe -m pytest -q pipeline/tests`.
The local `.venv` is ignored and contains only existing pipeline test requirements
plus numpy. No API translation, pipeline collection, embedding or production
deployment was run.

`baseline-results.json` is the original engine snapshot and a committed test fixture.
`npm run benchmark:search` generates the ignored local `implementation-results.json`,
recording new engine results, all concept parity checks and source validation.
`browser-checks.json` and `performance-results.json` record actual automated runs.
No nDCG/recall improvement is claimed without independently reviewed topic judgments.
The final browser run includes explorer pagination and filter-edit regressions,
and passed all 22 checks with no page errors. No production release has been performed; human
relevance and terminology review remain release gates.

Final review on November 23 fixed two gaps before rerunning the frontend checks:
keyboard correction no longer stops when a recognized concept appears beside an
unknown Latin span, and URL edits no longer silently discard invalid filters or
accept stale cluster meanings. All 50 corpus cases were rerun; five exact-identity
cases pass, and topic relevance judgments remain explicitly unreviewed. The
unchanged pipeline suite's recorded result is from the earlier implementation run.
The final performance change removed duplicate record scans. All 50 corpus cases
match an independent full-record scan exactly, including scores and evidence.
The saved pre-change run's worst p95 was 112.9 ms; the final run measured 13.3 ms.
Cold startup and coarse input/update timings remain separately reported.

## Branch contents

The delivery includes application code, the lockfile, tests, validation scripts, CI
and supporting documentation. Small browser/performance reports and the frozen
baseline are retained as review evidence. The unrelated OpenAlex design note,
regenerable full implementation-results dump, local dependencies, virtual environment
and build output are omitted from the branch. Omitted local files are preserved.

## Practical limitations

- Cold indexing still has a measurable main-thread cost and the full papers dataset
  is still eagerly loaded. A prebuilt index alone would add payload; lazy detail
  loading is the separate future phase.
- 64 concepts are limited coverage. Existing generated label translations remain
  a lower-priority literal fallback; aliases do not imply arbitrary semantic search.
- Scientific compound/plural spellings need explicit reviewed aliases. Ambiguous
  ML/AI/PDE remain literal instead of guessed meanings.
- The browser cannot see the private curation review map or identify a specific
  bad title from a lab-level flag. It labels and downranks dependent evidence while
  retaining valid identity matches.
- Optional semantic retrieval, broad typo tolerance, compact export and lazy paper
  loading remain outside this implementation, as scoped in the plan.
