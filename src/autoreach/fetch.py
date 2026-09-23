import hashlib
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger("autoreach")

USER_AGENT = "AutoReachBot/0.1 (+https://github.com/RyanNguyen173/AutoReach)"


class RobotsDisallowed(Exception):
    pass


class Fetcher:
    def __init__(self, cache_dir: Path | str = ".cache/html", delay: float = 1.0,
                 use_cache: bool = True, timeout: float = 20.0):
        self.cache_dir = Path(cache_dir)
        self.delay = delay
        self.use_cache = use_cache
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=timeout)
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}
        self.requests_made = 0

    def get_html(self, url: str, render: bool = False) -> str:
        path = self.cache_dir / (hashlib.sha1(f"{render}:{url}".encode()).hexdigest() + ".html")
        if self.use_cache and path.exists():
            log.info("cache hit  %s", url)
            return path.read_text(encoding="utf-8")

        if not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt does not allow fetching {url}")
        self._wait(url)
        log.info("fetching   %s%s", url, " (rendered)" if render else "")
        html = self._render(url) if render else self._get(url)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return html

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            rp = RobotFileParser()
            try:
                resp = self.client.get(origin + "/robots.txt")
                if resp.status_code >= 400:
                    # A missing or blocked robots.txt (401/403/404/...) means no
                    # restrictions were published, per how major crawlers behave.
                    rp.allow_all = True
                else:
                    rp.parse(resp.text.splitlines())
            except httpx.HTTPError:
                rp.allow_all = True
            self._robots[origin] = rp
        return self._robots[origin].can_fetch(USER_AGENT, url)

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request[host] = time.monotonic()
        self.requests_made += 1

    def _get(self, url: str) -> str:
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.text

    def _render(self, url: str) -> str:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError('Rendering needs Playwright: pip install "autoreach[render]"') from e
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get("AUTOREACH_CHROMIUM") or None)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto(url, wait_until="networkidle")
                    return page.content()
                finally:
                    browser.close()
        except PlaywrightError as e:
            # A hung/slow/unreachable site shouldn't take the whole batch
            # down - let callers handle this the same as an HTTP error.
            raise RuntimeError(str(e).splitlines()[0]) from e
