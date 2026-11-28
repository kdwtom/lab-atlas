# Concept dictionary review

Version `2026-11-21.1` contains 64 corpus-backed concepts across life science,
chemistry, physics, mathematics and computer science. Each entry records an actual
keyword or paper-title source, lab ID, paper ID where applicable, aliases, and reviewer.

The initial review was performed by **Codex**, not a human scientific translator.
`approved` means agent-reviewed for this implementation. Human domain review remains
outstanding. No human review or measured topic relevance is claimed. The local
implementation enables these entries for automated evaluation; this does not
satisfy the original plan's human-review release gate. The user's preference for
automated phone/IME checks does not waive that separate review requirement.

The vocabulary keeps ML, deep learning, neural networks and GNN distinct. Ambiguous
ML/AI/PDE abbreviations remain literal; GNN, RNA and MOF use explicit scientific
aliases. Longest phrases consume nested spans without expanding related concepts.
Korean spacing is allowed at listed segment boundaries. Original corpus records are
used for concept recognition; existing generated Korean labels are only residual
literal fallback, never automatically promoted to concept equivalences.

Maintenance: review new entries against source records and narrow meaning, preserve
stable IDs, record reviewer/date, reject collisions, bump version, run unit tests and
the bilingual equivalence benchmark. Human reviewers should especially check Korean
term breadth, colloquial synonyms and abbreviation assumptions. Uncovered terms
retain literal matching; related IDs never alter retrieval.
