from autoreach.crawl import run_batch
from autoreach.fetch import RobotsDisallowed


class FakeFetcher:
    """A stand-in for Fetcher that serves canned HTML per URL instead of
    making real requests, so run_batch can be tested without a network."""

    def __init__(self, pages: dict[str, str], blocked: set[str] = frozenset()):
        self.pages = pages
        self.blocked = blocked

    def get_html(self, url: str, render: bool = False) -> str:
        if url in self.blocked:
            raise RobotsDisallowed(f"robots.txt does not allow fetching {url}")
        if url not in self.pages:
            raise RuntimeError(f"no fake page for {url}")
        return self.pages[url]


HOMEPAGE_WITH_STAFF = """
<html><body><nav><a href="https://a.example/staff-directory">Staff Directory</a></nav></body></html>
"""
STAFF_PAGE = """
<html><body>
<table><tr><th>Name</th><th>Title</th><th>Email</th></tr>
<tr><td>Nina Osei</td><td>Principal</td><td>nosei@a.example</td></tr>
</table>
</body></html>
"""
HOMEPAGE_NO_STAFF = """
<html><body><nav><a href="https://b.example/about">About</a></nav></body></html>
"""


def test_finds_directory_and_extracts_contacts_per_site():
    fetcher = FakeFetcher({
        "https://a.example": HOMEPAGE_WITH_STAFF,
        "https://a.example/staff-directory": STAFF_PAGE,
    })
    results = run_batch(["https://a.example"], fetcher)

    assert len(results) == 1
    r = results[0]
    assert r.directory_url == "https://a.example/staff-directory"
    assert [c.email for c in r.contacts] == ["nosei@a.example"]
    assert r.skips == []


def test_site_with_no_directory_link_is_skipped_not_fatal():
    fetcher = FakeFetcher({
        "https://a.example": HOMEPAGE_WITH_STAFF,
        "https://a.example/staff-directory": STAFF_PAGE,
        "https://b.example": HOMEPAGE_NO_STAFF,
    })
    results = run_batch(["https://a.example", "https://b.example"], fetcher)

    by_site = {r.site: r for r in results}
    assert by_site["https://b.example"].directory_url is None
    assert by_site["https://b.example"].contacts == []
    # the other site in the batch still succeeds
    assert len(by_site["https://a.example"].contacts) == 1


def test_robots_disallowed_homepage_is_recorded_not_raised():
    fetcher = FakeFetcher({}, blocked={"https://blocked.example"})
    results = run_batch(["https://blocked.example"], fetcher)

    assert len(results) == 1
    assert results[0].directory_url is None
    assert "robots.txt" in results[0].skips[0]
