from pathlib import Path

from autoreach.find_directory import find_directory_link

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_finds_an_explicit_staff_directory_link():
    url = find_directory_link(load("homepage_nav_finalsite.html"), "https://example.org/")
    assert url == "https://example.org/staff-directory"


def test_finds_a_meet_our_team_link():
    url = find_directory_link(load("homepage_nav_ambiguous.html"), "https://example.org/")
    assert url == "https://example.org/team"


def test_no_confident_match_returns_none():
    url = find_directory_link(load("homepage_nav_no_directory.html"), "https://example.org/")
    assert url is None


def test_bare_contact_link_alone_is_not_confident():
    """A lone "Contact" or "Connect with Us" link is genuinely ambiguous -
    it might be a contact form with no roster (the common case) or, on some
    sites (e.g. Hale HS), the actual staff directory. Without a stronger
    signal (an on-the-nose URL path, or a phrase like "Staff Directory"),
    this heuristic intentionally doesn't guess - that's real-world ambiguity
    the roadmap's planned AI fallback is meant to resolve, not this."""
    html = '<html><body><nav><a href="/connect">Connect with Us</a></nav></body></html>'
    assert find_directory_link(html, "https://example.org/") is None


def test_works_with_a_local_file_path_as_base_url():
    """A saved local file (e.g. "homepage.html") has no real origin to
    compare links against - urlparse gives it an empty host, so the
    same-origin filter must not reject every link as a result."""
    url = find_directory_link(load("homepage_nav_finalsite.html"), "tests/fixtures/homepage_nav_finalsite.html")
    assert url == "/staff-directory"


def test_ignores_off_site_and_file_links():
    html = """
    <html><body><nav>
      <a href="https://other-site.org/staff-directory">Staff Directory</a>
      <a href="/roster.pdf">Staff Directory PDF</a>
      <a href="/staff">Staff</a>
    </nav></body></html>
    """
    assert find_directory_link(html, "https://example.org/") == "https://example.org/staff"
