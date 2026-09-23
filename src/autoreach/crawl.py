"""Fetch a directory page (and its pagination) and extract contacts from it.

Shared by the `extract` and `batch` CLI commands so pagination/error
handling isn't duplicated between a single-site run and a multi-site one.
"""
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from .ai_fallback import find_directory_via_ai
from .extract import extract_contacts, find_page_links
from .fetch import Fetcher, RobotsDisallowed
from .find_directory import find_directory_link
from .models import Contact


class HtmlFetcher(Protocol):
    """What crawl_directory/run_batch need from a Fetcher - just enough to
    let tests use a lightweight fake instead of making real requests."""
    def get_html(self, url: str, render: bool = False) -> str: ...


def describe_fetch_error(e: Exception, url: str, render: bool) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        msg = f"HTTP {status} fetching {url}"
        if status in (403, 429) and not render:
            msg += " - the site may be blocking non-browser requests; try again with --render"
        return msg
    return f"Could not fetch {url}: {e}"


def crawl_directory(
    fetcher: HtmlFetcher, start_url: str, pages: int = 1, render: bool = False,
) -> tuple[list[Contact], list[str], int]:
    """Follow a directory's "Next"/A-Z/pagination links up to `pages` pages,
    extracting contacts from each. Fetch failures (robots.txt, HTTP errors)
    are collected as messages rather than raised, so one bad page doesn't
    stop a run over many sites. Returns (contacts, skip_messages, fetched)."""
    contacts: list[Contact] = []
    skips: list[str] = []
    queue, seen = [start_url], set()
    fetched = 0
    while queue and fetched < pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            html = fetcher.get_html(url, render=render)
        except RobotsDisallowed as e:
            skips.append(str(e))
            continue
        except (httpx.HTTPError, RuntimeError) as e:
            skips.append(describe_fetch_error(e, url, render))
            continue
        fetched += 1
        contacts.extend(extract_contacts(html, url))
        queue.extend(u for u in find_page_links(html, url) if u not in seen)
    return contacts, skips, fetched


def dedupe(contacts: list[Contact]) -> list[Contact]:
    unique: dict[str, Contact] = {}
    for c in contacts:
        unique.setdefault(c.email or c.contact_form_url, c)
    return list(unique.values())


@dataclass
class SiteResult:
    site: str
    directory_url: str | None = None
    contacts: list[Contact] = field(default_factory=list)
    skips: list[str] = field(default_factory=list)


def run_batch(
    sites: list[str], fetcher: HtmlFetcher, pages: int = 1, render: bool = False,
) -> list[SiteResult]:
    """find-directory + crawl_directory for each of a list of homepages.
    One site's failure (can't fetch, no directory found, robots.txt) doesn't
    stop the rest - each site's own SiteResult.skips records what happened."""
    results = []
    for site in sites:
        result = SiteResult(site=site)
        try:
            homepage_html = fetcher.get_html(site, render=render)
        except RobotsDisallowed as e:
            result.skips.append(str(e))
            results.append(result)
            continue
        except (httpx.HTTPError, RuntimeError) as e:
            result.skips.append(describe_fetch_error(e, site, render))
            results.append(result)
            continue

        result.directory_url = find_directory_link(homepage_html, site)
        if result.directory_url is None:
            result.directory_url = find_directory_via_ai(homepage_html, site)
        if result.directory_url is None:
            results.append(result)
            continue

        result.contacts, skips, _ = crawl_directory(fetcher, result.directory_url, pages=pages, render=render)
        result.skips.extend(skips)
        results.append(result)
    return results
