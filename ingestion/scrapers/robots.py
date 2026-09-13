"""
Robots.txt compliance guard — fail-closed robots.txt fetch/parse.

The airindex web-scraping spec ("compliance-first", "determine the actual
compliant access method and mark UNAVAILABLE sources honestly") requires
every adapter to check a source's robots.txt and never crawl paths that
are disallowed.

Design:
  - Fetch is done via stdlib urllib first and httpx as a fallback, so the
    module works in the offline build sandbox (no network: fail-closed
    with an explicit reason) as well as in a deployed environment.
  - Parsing uses urllib.robotparser (no bypass logic of any kind).
  - Fail-closed policy: if robots.txt cannot be fetched or parsed, the
    source is treated as NOT allowed for the requested path (it may also
    mean "edge is scraping a robots.txt gated on anti-bot" — which is the
    correct honest signal for Air India, per docs/ROBOTS_TXT_FINDINGS.md).
  - Results are memoized in this process (dict keyed by netloc+path) with
    a short TTL so a scheduler loop doesn't re-fetch robots.txt for every
    route; the daily compliance-check job deliberately bypasses the cache
    (force=True) so changes to robots.txt are picked up.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

DEFAULT_USER_AGENT = "AirIndexIndiaBot/1.0"

_CACHE_TTL_SECONDS = 3600  # 1 hour


@dataclass
class RobotsVerdict:
    allowed: bool
    reason: str
    crawl_delay_seconds: float | None = None
    checked_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "crawl_delay_seconds": self.crawl_delay_seconds,
            "checked_at": self.checked_at,
        }


def _fetch_robots_txt(robots_url: str, user_agent: str, timeout: float = 8.0) -> str | None:
    """Fetch robots.txt. Returns text or None (unreachable/unparseable)."""
    # Prefer httpx; fall back to urllib.request for stdlib-only contexts.
    try:
        resp = httpx.get(
            robots_url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text
        if resp.status_code in (403, 404):
            # 404 => no robots.txt (implies allowed); 403/other edge blocks
            # fall through and are handled by the caller's fail-closed rule.
            if resp.status_code == 404:
                return ""
            return None
        return None
    except Exception:
        try:
            from urllib.request import Request, urlopen

            req = Request(robots_url, headers={"User-Agent": user_agent})
            with urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="replace")
        except Exception:
            return None
        return None


class RobotFileParserNoRaise(urllib.robotparser.RobotFileParser):
    """RobotFileParser that behaves like urllib's but never raises on
    malformed contents (robotparser already tolerates most; this adds a
    defensive net so a proxy error page can never crash a collection run)."""

    def read(self, s=None):
        if s is None:
            self.url = self.url
            s = _fetch_robots_txt(self.url_url if hasattr(self, "url_url") else self.url, "*")
            if s is None:
                return
        super().parse((s or "").splitlines())

    def set_url(self, url: str):
        super().set_url(url)
        self.url_url = url


class RobotsTxtPolicy:
    """Fail-closed robots.txt checker with in-process memoization.

    `check(netloc_or_base_url, path)` returns a RobotsVerdict. When the
    file cannot be fetched the verdict is `allowed=False` with a reason
    string the adapter surfaces as its SOURCE_UNAVAILABLE detail.
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self._cache: dict[str, tuple[float, str, RobotFileParserNoRaise | None]] = {}

    def _adapter(self, robots_url: str, force: bool = False):
        key = robots_url
        now = time.time()
        cached = self._cache.get(key)
        if cached and not force and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1], cached[2]

        text = _fetch_robots_txt(robots_url, self.user_agent)
        state = "404" if text == "" else ("ok" if text is not None else "unreachable")
        parser = None
        if text is not None:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse((text or "").splitlines())
        self._cache[key] = (now, state, parser)
        return state, parser

    def _path_allowed(self, parser: RobotFileParserNoRaise | None, path: str) -> bool:
        if parser is None:
            return False  # fail closed
        try:
            return parser.can_fetch(self.user_agent, path)
        except Exception:
            return False

    @classmethod
    def robots_url_for(cls, base_url: str) -> str:
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def check(self, base_url: str, path: str, force: bool = False) -> RobotsVerdict:
        robots_url = self.robots_url_for(base_url)
        state, parser = self._adapter(robots_url, force=force)
        if state == "unreachable":
            return RobotsVerdict(
                allowed=False,
                reason=f"robots.txt unreachable for {robots_url} (edge/anti-bot block or network error)",
            )
        if state == "404":
            # No robots.txt => the standard allows crawling (subject to ToS).
            return RobotsVerdict(allowed=True, reason="no robots.txt (200/404 semantics: allowed)")
        allowed = self._path_allowed(parser, path)
        delay = None
        if parser is not None:
            try:
                delay = parser.crawl_delay(self.user_agent)
            except Exception:
                delay = None
        if not allowed:
            return RobotsVerdict(
                allowed=False,
                reason=f"path {path} is disallowed by {robots_url}",
                crawl_delay_seconds=delay,
            )
        return RobotsVerdict(allowed=True, reason=f"path {path} allowed", crawl_delay_seconds=delay)

    def invalidate(self, base_url: str) -> None:
        self._cache.pop(self.robots_url_for(base_url), None)


# Single reusable policy instance; adapters may also construct their own
# (with a custom UA) — this one is used by the scheduler compliance job.
GLOBAL_ROBOTS_POLICY = RobotsTxtPolicy()