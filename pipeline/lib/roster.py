"""Institution author rosters for matching (PLAN_PHASE1.md 0-4).

One OpenAlex filter query per institution (last_known_institutions = the institution, works_count > 4)
replaces a name search per professor: a list page of 200 authors costs 1 credit, a search costs 10.
Responses are not kept in the raw cache (about 11 KB per author); a compact copy with only the fields
the matcher reads is stored in cache/rosters/<institution id>.json.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from .. import config
from .names import SURNAME_ROMANIZATIONS, given_name_compatible, korean_surname, name_tokens, names_compatible, \
    surname_compatible
from .openalex import OpenAlex, short_id

log = logging.getLogger(__name__)
ROSTER_DIR = config.CACHE_DIR / "rosters"
MIN_WORKS = 5   # selection needs >= 4-5 papers in the window, so smaller profiles cannot qualify
SELECT = "id,display_name,display_name_alternatives,orcid,works_count,affiliations,last_known_institutions,topics"
MAX_ALTERNATIVES = 20


def compact(author: dict, inst_id: str) -> dict:
    """Keep the author fields evaluate() reads, in the same shape as a full OpenAlex author object."""
    return {
        "id": author["id"],
        "display_name": author.get("display_name"),
        "display_name_alternatives": (author.get("display_name_alternatives") or [])[:MAX_ALTERNATIVES],
        "orcid": author.get("orcid"),
        "works_count": author.get("works_count") or 0,
        "affiliations": [{"institution": {"id": (a.get("institution") or {}).get("id")}, "years": a.get("years") or []}
                         for a in author.get("affiliations") or []
                         if short_id((a.get("institution") or {}).get("id")) == inst_id],
        "last_known_institutions": [{"id": i.get("id")} for i in author.get("last_known_institutions") or []],
        "topics": [{"count": t.get("count"), "domain": {"display_name": (t.get("domain") or {}).get("display_name")},
                    "field": {"display_name": (t.get("field") or {}).get("display_name")}}
                   for t in author.get("topics") or []],
    }


def load(oa: OpenAlex, inst_id: str) -> tuple[list[dict], date]:
    path = ROSTER_DIR / f"{inst_id}.json"
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        return d["authors"], date.fromisoformat(d["retrieved_at"])
    authors, cursor, day = [], "*", config.TODAY
    while cursor:
        data, day = oa.get("authors", filter=f"last_known_institutions.id:{inst_id},works_count:>{MIN_WORKS - 1}",
                           select=SELECT, cursor=cursor, store=False, **{"per-page": 200})
        results = (data or {}).get("results") or []
        authors += [compact(a, inst_id) for a in results]
        cursor = (data or {}).get("meta", {}).get("next_cursor") if results else None
    ROSTER_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"institution": inst_id, "retrieved_at": day.isoformat(), "authors": authors},
                               ensure_ascii=False), encoding="utf-8")
    log.info("roster %s: %d authors", inst_id, len(authors))
    return authors, day


def all_names(author: dict) -> list[str]:
    return [n for n in [author.get("display_name") or ""] + list(author.get("display_name_alternatives") or []) if n]


class Roster:
    """Name lookup over one institution's authors."""

    def __init__(self, authors: list[dict]):
        self.authors = authors
        self.by_token: dict[str, set[int]] = defaultdict(set)
        for i, a in enumerate(authors):
            for n in all_names(a):
                for t in name_tokens(n):
                    if len(t) > 1:
                        self.by_token[t].add(i)

    def _pool(self, tokens: set[str]) -> list[dict]:
        idx: set[int] = set()
        for t in tokens:
            idx |= self.by_token.get(t, set())
        return [self.authors[i] for i in sorted(idx)]

    def candidates(self, name_en: Optional[str], name_ko: Optional[str]) -> list[dict]:
        """Authors whose display name or an alternative is compatible with the professor's name."""
        if name_en:
            pool = self._pool({t for t in name_tokens(name_en) if len(t) > 1})
            return [a for a in pool if any(names_compatible(name_en, n) for n in all_names(a))]
        sur = korean_surname(name_ko or "")
        if not sur or sur not in SURNAME_ROMANIZATIONS:
            return []
        out = []
        for a in self._pool(SURNAME_ROMANIZATIONS[sur]):
            names = [n for n in all_names(a) if surname_compatible(name_ko, n)]
            if any(given_name_compatible(name_ko, n) is not False for n in names):
                out.append(a)
        return out
