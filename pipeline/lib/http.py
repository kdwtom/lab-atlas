"""Cached, rate-limited HTTP client.

Every response body is cached under pipeline/cache/<namespace>/<sha1>.json together with the
request URL and fetch date, so re-runs never hit the network for the same request.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import requests

from .. import config

log = logging.getLogger(__name__)

try:  # use the OS trust store (same behaviour as the user's browser, incl. Windows)
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    log.debug("truststore not available; falling back to certifi")


class FetchError(RuntimeError):
    pass


class QuotaExceeded(FetchError):
    """Daily quota exhausted (429 with a very long Retry-After). Re-run after the reset; the cache keeps progress."""


MAX_RETRY_AFTER = 300  # seconds; longer waits mean a daily quota, not a transient rate limit


class CachedClient:
    def __init__(self, cache_dir: Path = config.CACHE_DIR, offline: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline
        self.session = requests.Session()
        # mailto is sent only to OpenAlex as a query parameter, never to university sites.
        self.session.headers["User-Agent"] = config.USER_AGENT
        self._last_call: dict[str, float] = {}
        self.stats = {"cache_hits": 0, "network": 0, "errors": 0}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def build_url(url: str, params: Optional[dict[str, Any]] = None) -> str:
        if not params:
            return url
        clean = {k: v for k, v in params.items() if v is not None}
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urlencode(clean, safe=':,|*')}"

    def _cache_path(self, namespace: str, key: str) -> Path:
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.cache_dir / namespace / h[:2] / f"{h}.json"

    def _throttle(self, host: str, min_interval: float) -> None:
        last = self._last_call.get(host, 0.0)
        wait = min_interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_call[host] = time.monotonic()

    # ------------------------------------------------------------------ core
    def fetch(
        self,
        url: str,
        *,
        namespace: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        json_body: Any = None,
        headers: Optional[dict[str, str]] = None,
        min_interval: float = config.WEB_MIN_INTERVAL,
        cache_key_exclude: tuple[str, ...] = ("mailto",),
        retries: int = 4,
        allow_404: bool = False,
    ) -> dict[str, Any]:
        """Return cached entry: {url, status, body(text), fetched_at}."""
        full_url = self.build_url(url, params)
        key_params = {k: v for k, v in (params or {}).items() if k not in cache_key_exclude}
        key = method + " " + self.build_url(url, key_params)
        if json_body is not None:
            key += " " + json.dumps(json_body, sort_keys=True, ensure_ascii=False)
        path = self._cache_path(namespace, key)
        if path.exists():
            self.stats["cache_hits"] += 1
            return json.loads(path.read_text(encoding="utf-8"))
        if self.offline:
            raise FetchError(f"offline mode and not cached: {full_url}")

        host = urlparse(url).netloc
        backoff = 2.0
        last_err: Optional[str] = None
        for attempt in range(retries + 1):
            self._throttle(host, min_interval)
            try:
                resp = self.session.request(
                    method, full_url, json=json_body, headers=headers, timeout=config.HTTP_TIMEOUT
                )
                self.stats["network"] += 1
            except requests.RequestException as e:
                last_err = f"{type(e).__name__}: {e}"
                log.warning("request failed (%s/%s) %s: %s", attempt + 1, retries + 1, full_url, last_err)
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                if resp.status_code == 429 and delay > MAX_RETRY_AFTER:
                    self.stats["errors"] += 1
                    raise QuotaExceeded(f"quota exhausted for {host}; resets in {delay / 3600:.1f}h")
                log.warning("HTTP %s for %s; retry in %.1fs", resp.status_code, full_url, delay)
                time.sleep(delay)
                backoff *= 2
                last_err = f"HTTP {resp.status_code}"
                continue
            if resp.status_code >= 400 and not (allow_404 and resp.status_code == 404):
                self.stats["errors"] += 1
                raise FetchError(f"HTTP {resp.status_code} for {full_url}: {resp.text[:200]}")
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            entry = {
                "url": resp.url,
                "request": key,
                "status": resp.status_code,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "body": resp.text,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            return entry
        self.stats["errors"] += 1
        raise FetchError(f"giving up on {full_url}: {last_err}")

    # ------------------------------------------------------------------ conveniences
    def get_html(self, url: str, params: Optional[dict[str, Any]] = None) -> tuple[str, str, date]:
        e = self.fetch(url, namespace="web", params=params, min_interval=config.WEB_MIN_INTERVAL)
        return e["body"], e["url"], datetime.fromisoformat(e["fetched_at"]).date()

    def get_json(self, url: str, *, namespace: str, params=None, min_interval: float, **kw) -> tuple[Any, date]:
        e = self.fetch(url, namespace=namespace, params=params, min_interval=min_interval, **kw)
        body = json.loads(e["body"]) if e["body"] else None
        return body, datetime.fromisoformat(e["fetched_at"]).date()
