"""Locate a school or company's staff directory page from its homepage.

Phase 2 of the roadmap: given just a homepage, find the page extract()
should be pointed at, instead of requiring the directory URL up front.
"""
import re
from urllib.parse import urljoin, urldefrag, urlparse

from bs4 import BeautifulSoup

# Phrases that, on their own, are a strong signal a link leads to a staff
# directory ("Staff Directory", "Meet Our Staff") rather than just any page
# that happens to mention staff in passing.
_STRONG_PHRASES = (
    "staff directory", "faculty directory", "employee directory",
    "staff & faculty", "faculty & staff", "staff and faculty", "faculty and staff",
    "meet the staff", "meet our staff", "meet the faculty", "meet our faculty",
    "meet the team", "meet our team", "our staff", "our faculty", "our team",
)
# Weaker signals - either a single word that shows up in lots of unrelated
# nav items ("Team" sports pages, a "Contact" page with no roster), or a
# phrase that's real on some sites (a school's directory titled "Connect
# with Us") but ambiguous with an ordinary contact-form page elsewhere.
_WEAK_PHRASES = (
    "staff", "faculty", "directory", "personnel", "team", "people",
    "administration", "contact", "connect with us",
)

_PATH_RE = re.compile(r"staff|faculty|directory|personnel|roster", re.I)

_SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".doc", ".docx", ".xlsx")


def _score(text: str, path: str) -> int:
    text = text.strip().lower()
    score = 0
    if any(p in text for p in _STRONG_PHRASES):
        score += 10
    elif any(p in text for p in _WEAK_PHRASES):
        score += 3
    if _PATH_RE.search(path):
        score += 5
    return score


def candidate_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Every same-origin, non-asset link on the page as (visible text, URL) -
    the pool find_directory_link scores, and what the AI fallback picks from
    when the heuristic can't decide."""
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(base_url).netloc
    # A saved local file has no real origin to compare against - relative
    # links on the page still point at the original site, so same-origin
    # filtering would reject every one of them. Only enforce it when
    # base_url is an actual URL.
    check_origin = bool(host)
    seen: set[str] = set()
    links = []

    for a in soup.find_all("a", href=True):
        url = urldefrag(urljoin(base_url, a["href"]))[0]
        parsed = urlparse(url)
        off_site = check_origin and (parsed.netloc != host or parsed.scheme not in ("http", "https"))
        if off_site or url in seen:
            continue
        if parsed.path.lower().endswith(_SKIP_EXTENSIONS):
            continue
        seen.add(url)
        links.append((a.get_text(" ", strip=True), url))

    return links


def find_directory_link(html: str, base_url: str) -> str | None:
    """The single most likely staff-directory URL linked from this homepage,
    or None if nothing looks like one. Prefers a strong text match ("Staff
    Directory") or an on-the-nose URL path (/staff, /directory) over a bare
    "Contact" or "Team" link, which are common false positives."""
    best_url, best_score = None, 0
    for text, url in candidate_links(html, base_url):
        score = _score(text, urlparse(url).path)
        if score > best_score:
            best_url, best_score = url, score
    return best_url if best_score >= 5 else None
