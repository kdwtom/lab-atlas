from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

ORCID_RE = re.compile(r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.I)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text(el: Optional[Tag]) -> Optional[str]:
    if el is None:
        return None
    t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
    return t or None


def abs_url(base: str, href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "#")) or href in ("", "#"):
        return None
    if href.startswith("www."):
        href = "http://" + href
    return urljoin(base, href)


def find_orcid(html: str) -> Optional[str]:
    m = ORCID_RE.search(html)
    return m.group(1).upper() if m else None


def clean_email(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.replace("mailto:", "").strip().lower()
    return s if "@" in s else None
