"""Text helpers: abstract reconstruction, title normalisation, citation parsing."""
from __future__ import annotations

import html
import re
from typing import Optional

from .names import strip_accents


def reconstruct_abstract(inv: Optional[dict[str, list[int]]]) -> Optional[str]:
    """Rebuild plain text from OpenAlex abstract_inverted_index."""
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort()
    text = " ".join(w for _, w in positions)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def norm_title(s: str) -> str:
    s = strip_accents(html.unescape(s)).lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_YEAR_PAREN = re.compile(r"\((?:19|20)\d{2}[a-z]?\)\.?\s*")


def title_from_citation(cit: str) -> str:
    """Best-effort title extraction from a free-text citation string.

    Handles: "Authors (2025) Title. Journal 16:1696"  (SNU)
             "Title, Journal, , 58, 1217-1235 (2025 )"  (POSTECH)
             "Title, 2022, Nature"                     (GIST)
             'Authors (2023) "Title", Journal'         (quoted title)
             "Title. / Authors. Journal"               (GIST, alternative)
             "A. B. Kim, and C. D. Lee*. Title. Journal" (SNU, no year)
    The result is only used as a search query; matches are verified against the full citation.
    """
    c = re.sub(r"\s+", " ", cit).strip()
    m = re.search(r"[\"“”](.{20,}?)[\"“”]", c)
    if m:
        return m.group(1).strip(" .,")
    if " / " in c and len(c.split(" / ", 1)[0]) >= 20:
        return c.split(" / ", 1)[0].strip(" .")
    m = re.search(r"\*\.\s+(?=[A-Z0-9])", c)  # author list ending with the corresponding mark
    if m and m.end() < len(c) - 15:
        rest = c[m.end():]
        return re.split(r"(?<=[a-z0-9\)])\.\s+(?=[A-Z])", rest, maxsplit=1)[0].strip(" .")
    m = _YEAR_PAREN.search(c)
    if m and m.start() > 10 and m.end() < len(c) - 15:  # authors (year) title. journal
        rest = c[m.end():]
        parts = re.split(r"(?<=[a-z0-9\)])\.\s+(?=[A-Z])", rest, maxsplit=1)
        return parts[0].strip(" .")
    m = re.search(r",\s*(?:19|20)\d{2}\s*,[^,]*$", c)  # title, 2022, Journal
    if m:
        return c[: m.start()].strip(" .,")
    m = re.search(r"\((?:19|20)\d{2}\s*\)\s*$", c)  # title, journal, , vol, pages (2025 )
    if m:
        parts = c[: m.start()].rsplit(", ", 4)
        if len(parts) == 5:
            return parts[0].strip(" .,")
    return c[:300]
