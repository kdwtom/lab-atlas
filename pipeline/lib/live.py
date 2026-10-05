"""Uncached HTTP for verification (stage 6): checks must see the sources as they are today.

Requests to the same host are spaced by `min_interval`; different hosts run in parallel.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests

from .. import config
from . import http as _http  # noqa: F401  (injects the OS trust store, same TLS behaviour as collection)


@dataclass
class Result:
    url: str
    status: Optional[int]      # None = no HTTP response
    final_url: Optional[str]
    error: Optional[str]
    body: str = ""

    @property
    def verdict(self) -> str:
        """ok | blocked (bot protection / auth; check by hand) | broken | unreachable"""
        if self.status is None:
            return "unreachable"
        if self.status < 400:
            return "ok"
        if self.status in (401, 403, 405, 429, 503):
            return "blocked"
        return "broken"


class LiveClient:
    def __init__(self, min_interval: float = 0.5):
        self.min_interval = min_interval
        self._local = threading.local()
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._last: dict[str, float] = {}

    def _session(self) -> requests.Session:
        s = getattr(self._local, "s", None)
        if s is None:
            s = self._local.s = requests.Session()
            s.headers["User-Agent"] = config.USER_AGENT
        return s

    def get(self, url: str, *, keep_body: bool = False, headers: Optional[dict] = None,
            timeout: float = 20) -> Result:
        host = urlparse(url).netloc
        with self._locks[host]:
            wait = self.min_interval - (time.monotonic() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()
        try:
            r = self._session().get(url, headers=headers, timeout=timeout, allow_redirects=True,
                                    stream=not keep_body)
            body = ""
            if keep_body:
                if not r.encoding or r.encoding.lower() == "iso-8859-1":
                    r.encoding = r.apparent_encoding or "utf-8"
                body = r.text
            r.close()
            return Result(url, r.status_code, r.url, None, body)
        except requests.RequestException as e:
            return Result(url, None, None, f"{type(e).__name__}: {str(e)[:160]}")


def openalex_params(**extra) -> dict:
    p = dict(extra)
    if config.OPENALEX_MAILTO:
        p["mailto"] = config.OPENALEX_MAILTO
    if config.OPENALEX_API_KEY:
        p["api_key"] = config.OPENALEX_API_KEY
    return p
