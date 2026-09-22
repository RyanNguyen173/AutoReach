import csv
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from typer.testing import CliRunner

from autoreach.cli import app
from autoreach.fetch import Fetcher, RobotsDisallowed

FIXTURES = Path(__file__).parent / "fixtures"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    (root / "staff").mkdir(parents=True)
    (root / "private").mkdir()
    (root / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    page1 = (FIXTURES / "table.html").read_text().replace(
        "</body>", '<a href="/staff/page2.html">Next</a></body>')
    (root / "staff" / "index.html").write_text(page1)
    (root / "staff" / "page2.html").write_text((FIXTURES / "cards.html").read_text())
    (root / "private" / "index.html").write_text((FIXTURES / "table.html").read_text())

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_robots_txt_is_respected(site, tmp_path):
    fetcher = Fetcher(cache_dir=tmp_path / "cache", delay=0)
    assert fetcher.allowed(f"{site}/staff/")
    with pytest.raises(RobotsDisallowed):
        fetcher.get_html(f"{site}/private/")


def test_robots_txt_blocked_by_server_means_no_restrictions(tmp_path):
    """A 401/403/404 fetching robots.txt itself (common with bot-blocking) is not
    a statement that the whole site is off-limits - it means none were published."""
    (tmp_path / "site").mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(tmp_path / "site")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        fetcher = Fetcher(cache_dir=tmp_path / "cache", delay=0)
        assert fetcher.allowed(f"http://127.0.0.1:{server.server_port}/staff")
    finally:
        server.shutdown()


def test_second_fetch_uses_cache(site, tmp_path):
    cache = tmp_path / "cache"
    first = Fetcher(cache_dir=cache, delay=0)
    first.get_html(f"{site}/staff/")
    assert first.requests_made == 1
    second = Fetcher(cache_dir=cache, delay=0)
    assert "Maria" in second.get_html(f"{site}/staff/")
    assert second.requests_made == 0


def test_cli_follows_pages_and_writes_csv(site, tmp_path):
    out = tmp_path / "contacts.csv"
    result = CliRunner().invoke(app, [
        "extract", f"{site}/staff/", "--pages", "3", "--delay", "0",
        "--cache-dir", str(tmp_path / "cache"), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(out.open()))
    emails = {r["email"] for r in rows}
    assert "mdelgado@example.org" in emails and "rchen@example.org" in emails
    assert list(rows[0]) == ["name", "title", "department", "email", "contact_form_url", "source_url"]


def test_cli_reads_saved_file(tmp_path):
    out = tmp_path / "contacts.csv"
    result = CliRunner().invoke(app, ["extract", str(FIXTURES / "obfuscated.html"), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert len(list(csv.DictReader(out.open()))) == 4


def test_cli_extract_reports_form_only_contacts(tmp_path):
    out = tmp_path / "contacts.csv"
    result = CliRunner().invoke(app, ["extract", str(FIXTURES / "form_links_directory.html"), "-o", str(out)])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 4
    assert all(r["email"] == "" and r["contact_form_url"] for r in rows)
    assert "4 reachable only through a contact form" in result.output


def test_cli_form_command_lists_fields(tmp_path):
    result = CliRunner().invoke(app, ["form", str(FIXTURES / "contact_form.html")])
    assert result.exit_code == 0, result.output
    assert "field_first" in result.output
    assert "Your First Name" in result.output


def test_cli_form_command_warns_about_captcha(tmp_path):
    result = CliRunner().invoke(app, ["form", str(FIXTURES / "contact_form.html")])
    assert "CAPTCHA" in result.output
