"""Thin OpenAlex API wrapper on top of CachedClient."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterator, Optional

from .. import config
from .http import CachedClient

AUTHOR_FIELDS = None  # full author objects are small enough


def short_id(oa_id: Optional[str]) -> Optional[str]:
    if not oa_id:
        return None
    return oa_id.rstrip("/").rsplit("/", 1)[-1]


def clean_search(q: str) -> str:
    """Drop characters OpenAlex search treats as syntax (wildcards; '*' often marks corresponding authors)."""
    return " ".join(re.sub(r"[*?\"“”]", " ", q).split())


class OpenAlex:
    def __init__(self, client: CachedClient):
        self.c = client
        self.mailto = config.require_mailto()

    def _params(self, **params: Any) -> dict[str, Any]:
        p = {k: v for k, v in params.items() if v is not None}
        p["mailto"] = self.mailto
        if config.OPENALEX_API_KEY:
            p["api_key"] = config.OPENALEX_API_KEY
        return p

    def get(self, path: str, **params: Any) -> tuple[Any, date]:
        return self.c.get_json(
            f"{config.OPENALEX_BASE}/{path.lstrip('/')}", namespace="openalex",
            params=self._params(**params), min_interval=config.OPENALEX_MIN_INTERVAL,
            cache_key_exclude=("mailto", "api_key"), allow_404=True,
        )

    # ------------------------------------------------------------------ entities
    def search_institutions(self, query: str) -> list[dict]:
        data, _ = self.get("institutions", search=query, filter="country_code:KR", **{"per-page": 10})
        return (data or {}).get("results", [])

    def search_authors(self, name: str, institution_id: Optional[str] = None) -> list[dict]:
        flt = f"affiliations.institution.id:{short_id(institution_id)}" if institution_id else None
        data, _ = self.get("authors", search=clean_search(name), filter=flt, **{"per-page": 25})
        return (data or {}).get("results", [])

    def author(self, author_id: str) -> tuple[Optional[dict], date]:
        return self.get(f"authors/{short_id(author_id)}")

    def search_works_by_title(self, title: str, per_page: int = 5) -> list[dict]:
        data, _ = self.get(
            "works", search=clean_search(title)[:400], select="id,display_name,publication_year,authorships",
            **{"per-page": per_page},
        )
        return (data or {}).get("results", [])

    def works_for_author(self, author_id: str, from_year: int) -> Iterator[tuple[dict, date]]:
        cursor = "*"
        select = ("id,doi,display_name,publication_year,publication_date,type,primary_location,"
                  "cited_by_count,authorships,abstract_inverted_index,topics")
        while cursor:
            data, day = self.get(
                "works",
                filter=f"author.id:{short_id(author_id)},from_publication_date:{from_year}-01-01",
                select=select, cursor=cursor, sort="publication_date:desc", **{"per-page": 200},
            )
            if not data:
                return
            for w in data.get("results", []):
                yield w, day
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not data.get("results"):
                break
