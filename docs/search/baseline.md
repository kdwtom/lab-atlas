# Search baseline

Frozen on 2026-11-21 at main `8d4d0496efbde3a5c222bec5bf5a59f97059e024`.
`benchmark.json` contains 50 queries and SHA-256 fingerprints. `baseline-results.json`
records complete IDs, order, scores and first-word reasons from the historical engine.
Its source is preserved in `web/tests/search/fixtures/legacy-search.ts`.

Reproduce with Node 24 from `web`: `node scripts/capture-search-baseline.mjs`.
The capture helper uses Node's built-in TypeScript stripping. The regular Vitest
test and benchmark commands remain compatible with the CI Node 20 environment.
The helper applies the specified filters to the old engine's complete result; it does
not claim that the old suggestion UI applied filters correctly.

Only five exact-identity judgments are verified from stored fields by Codex. Topic
relevance remains pending human review. No topic accuracy, nDCG, or corpus recall is
claimed. Candidate results must not automatically become positive judgments.

The zero/punctuation, RNA boundary, phrase coherence, keyboard correction, and
cross-view behaviors will additionally be covered by deterministic synthetic tests.
